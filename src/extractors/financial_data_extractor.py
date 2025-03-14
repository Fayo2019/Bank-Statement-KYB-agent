import os
from typing import Dict, List, Any
from src.utils.api_utils import get_completion
from src.utils.parsing import parse_amount

def extract_financial_data(images: List, model: str = os.getenv("OPENAI_MODEL", "gpt-4o")) -> Dict[str, Any]:
    """Extract transaction data and balance information with built-in reconciliation."""
    prompt = """Extract all financial information from this bank statement including:
    
    1. Opening balance with date
    2. Closing balance with date
    3. All transactions with:
       - Date
       - Description
       - Amount (negative for debits, positive for credits)
       - Running balance if available
    
    Please also include a single overall confidence score (0-1) indicating how confident you are 
    in the accuracy of the entire financial data extraction process.
    
    Return the data in a structured JSON with these categories:
    {
        "opening_balance": {"amount": "...", "date": "..."},
        "closing_balance": {"amount": "...", "date": "..."},
        "transactions": [
            {"date": "...", "description": "...", "amount": "...", "running_balance": "..."},
            ...
        ],
        "confidence": 0.92 // single overall confidence score for the entire extraction
    }
    """
    detailed_financial_data = get_completion(prompt, images, model=model, json_mode=True)
    
    # Process the extracted data
    if not detailed_financial_data:
        return {"confidence": 0, "error": "Failed to extract financial data"}
    
    # Store transactions for internal analysis
    transactions = detailed_financial_data.get("transactions", [])
    
    # Calculate totals
    total_deposits = sum(parse_amount(t.get("amount", 0)) for t in transactions 
                         if parse_amount(t.get("amount", 0)) > 0)
    total_withdrawals = sum(abs(parse_amount(t.get("amount", 0))) for t in transactions 
                           if parse_amount(t.get("amount", 0)) < 0)
    
    # Create summary data
    summary_data = {
        "opening_balance": detailed_financial_data.get("opening_balance", {}),
        "closing_balance": detailed_financial_data.get("closing_balance", {}),
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "transaction_count": len(transactions),
        "confidence": detailed_financial_data.get("confidence", 0.5),
        "_transactions_for_analysis": transactions
    }
    
    # Perform reconciliation as part of extraction
    try:
        opening_balance = parse_amount(summary_data.get('opening_balance', {}).get('amount', 0))
        closing_balance = parse_amount(summary_data.get('closing_balance', {}).get('amount', 0))
        transaction_net_change = sum(parse_amount(t.get('amount', 0)) for t in transactions)
        
        expected_closing = opening_balance + transaction_net_change
        matches = abs(expected_closing - closing_balance) < 0.01
        
        summary_data["reconciliation"] = {
            "matches": matches,
            "expected_closing_balance": expected_closing,
            "reported_closing_balance": closing_balance,
            "discrepancy": closing_balance - expected_closing
        }
    except Exception as e:
        summary_data["reconciliation"] = {
            "matches": False,
            "error": str(e)
        }
    
    # Check for suspicious patterns
    suspicious_patterns = []
    
    # Check for identical zero balances
    if abs(opening_balance) < 0.01 and abs(closing_balance) < 0.01:
        suspicious_patterns.append("Both opening and closing balances are zero (0.00)")
    
    # Check for no transactions but balance change
    if len(transactions) == 0 and abs(closing_balance - opening_balance) > 0.01:
        suspicious_patterns.append("Balance changed with no transactions recorded")
    
    # Check for transactions but no balance change when there should be
    if len(transactions) > 0 and abs(closing_balance - opening_balance) < 0.01 and abs(transaction_net_change) > 0.01:
        suspicious_patterns.append("Transactions present but opening and closing balances are identical")
    
    # Check for round number transactions
    round_transactions = [t for t in transactions 
                          if abs(parse_amount(t.get('amount', 0)) % 1000) < 0.01 
                          and abs(parse_amount(t.get('amount', 0))) >= 1000]
    if len(round_transactions) > 2:
        suspicious_patterns.append(f"Multiple large round-number transactions: {len(round_transactions)} found")
    
    summary_data["suspicious_patterns"] = {
        "suspicious_patterns_found": len(suspicious_patterns) > 0,
        "suspicious_patterns": suspicious_patterns
    }
    
    return summary_data 