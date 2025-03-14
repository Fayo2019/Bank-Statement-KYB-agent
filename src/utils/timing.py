import time
from typing import Callable, Any, Dict, List

def time_process(process_name: str, func: Callable, *args, verbose: bool = False, **kwargs) -> Any:
    """Execute a function and time it, printing start/end messages if verbose is True."""
    if verbose:
        print(f"\nStarting process: {process_name}")
        start_time = time.time()
    
    result = func(*args, **kwargs)
    
    if verbose:
        elapsed_time = time.time() - start_time
        print(f"Completed process: {process_name} - Time: {elapsed_time:.2f} seconds")
        
        # Print relevant output details based on the process type
        if process_name == "PDF to Images Conversion" and isinstance(result, list):
            print(f"Pages Converted: {len(result)}")
            
        elif process_name == "PDF Metadata Extraction" and isinstance(result, dict):
            print(f"Pages: {result.get('Pages', 'Unknown')}")
            print(f"Metadata Found: {result.get('Metadata Found', False)}")
            if result.get('Title'):
                print(f"Title: {result.get('Title', 'Not available')}")
            if result.get('Author'):
                print(f"Author: {result.get('Author', 'Not available')}")
            if result.get('Creator'):  
                print(f"Creator: {result.get('Creator', 'Not available')}")
            
        elif process_name == "Document Type Analysis" and isinstance(result, dict):
            print(f"Result: {result.get('document_type', 'Unknown')}")
            print(f"Is Bank Statement: {result.get('is_bank_statement', False)}")
            print(f"Confidence: {result.get('confidence', 0):.2f}")
            if result.get('evidence', []):
                print("Evidence:")
                if isinstance(result.get('evidence'), list):
                    for evidence_item in result.get('evidence', []):
                        print(f"  - {evidence_item}")
                else:
                    print(f"  - {result.get('evidence')}")
            if result.get('bank_name'):
                print(f"Bank Name: {result.get('bank_name', 'Not found')}")
            
        elif process_name == "Business Details Extraction" and isinstance(result, dict):
            print(f"Business Name: {result.get('business_name', 'Not found')}")
            print(f"Account Number: {result.get('account_number', 'Not found')}")
            
        elif process_name == "Financial Data Extraction" and isinstance(result, dict):
            opening = result.get('opening_balance', {})
            closing = result.get('closing_balance', {})
            print(f"Opening Balance: {opening.get('amount', 'Not found')} ({opening.get('date', 'No date')})")
            print(f"Closing Balance: {closing.get('amount', 'Not found')} ({closing.get('date', 'No date')})")
            print(f"Total Deposits: {result.get('total_deposits', 'Not calculated')}")
            print(f"Total Withdrawals: {result.get('total_withdrawals', 'Not calculated')}")
            print(f"Transaction Count: {result.get('transaction_count', 0)}")
            # Don't print individual transactions
            
        elif "reconciliation" in process_name and isinstance(result, dict):
            if "matches" in result:
                print(f"Reconciliation Match: {result.get('matches', False)}")
                if not result.get('matches', True):
                    print(f"Discrepancy: {result.get('discrepancy', 'N/A')}")
            else:
                print(f"Reconciliation Not Possible: {result.get('error', 'Unknown reason')}")
                
        elif "suspicious_patterns" in process_name and isinstance(result, dict):
            print(f"Suspicious Financial Patterns Found: {result.get('suspicious_patterns_found', False)}")
            for pattern in result.get('suspicious_patterns', []):
                print(f"  - {pattern}")
                
        elif process_name == "Visual Tampering Detection" and isinstance(result, dict):
            print(f"Tampering Detected: {result.get('tampering_detected', False)}")
            print(f"Confidence: {result.get('confidence', 0):.2f}")
            if result.get('evidence', []):
                print(f"Evidence found: {len(result.get('evidence', []))} items")
                # Show first 3 evidence items
                for i, evidence_item in enumerate(result.get('evidence', [])[:3]):
                    print(f"  - {evidence_item}")
                if len(result.get('evidence', [])) > 3:
                    print(f"  - Plus {len(result.get('evidence', [])) - 3} more evidence items...")
            
        elif process_name == "PDF Structure Analysis" and isinstance(result, dict):
            print(f"Issues Detected: {result.get('issues_detected', False)}")
            print(f"Confidence: {result.get('confidence', 0):.2f}")
            
            if result.get('findings', []):
                findings = result.get('findings', [])
                print(f"Found {len(findings)} issues")
                for finding in findings[:min(3, len(findings))]:
                    print(f"  - {finding}")
                if len(findings) > 3:
                    print(f"  - Plus {len(findings) - 3} more findings...")
            
            if result.get('reasoning'):
                reasoning = result.get('reasoning')
                print(f"LLM Reasoning: {reasoning[:100]}..." if len(reasoning) > 100 else f"LLM Reasoning: {reasoning}")
                
        elif process_name == "Fraud Risk Assessment" and isinstance(result, dict):
            print(f"Risk Level: {result.get('risk_level', 'Unknown')}")
            print(f"Risk Score: {result.get('risk_score', 0):.2f}")
            print(f"Confidence: {result.get('confidence', 0):.2f}")
            
            if result.get('risk_factors', []):
                print("Risk Factors:")
                for factor in result.get('risk_factors', []):
                    print(f"  - {factor}")
                    
            if result.get('component_details', {}):
                print("\nComponent Risk Details:")
                for component_name, details in result.get('component_details', {}).items():
                    if details.get('risk_score', 0) > 0:
                        print(f"  {component_name.replace('_', ' ').title()}:")
                        print(f"    Score: {details.get('risk_score', 0):.2f}")
                        print(f"    Confidence: {details.get('confidence', 0):.2f}")
                        
                        # Show sample evidence
                        evidence = details.get('evidence', [])
                        if evidence:
                            print(f"    Sample Evidence ({min(3, len(evidence))} of {len(evidence)}):")
                            for i, item in enumerate(evidence[:3]):
                                print(f"      - {item}")
                            if len(evidence) > 3:
                                print(f"      - Plus {len(evidence) - 3} more evidence items...")
            
        print()  # Extra empty line after each process
    
    return result 