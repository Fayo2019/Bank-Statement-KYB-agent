from typing import Dict, Any
from src.utils.parsing import print_section_header

def print_analysis_summary(analysis: Dict[str, Any]) -> None:
    """Print a human-readable executive summary of the analysis."""
    print_section_header("BANK STATEMENT VERIFICATION - EXECUTIVE RISK PROFILE")
    
    doc_analysis = analysis.get("document_analysis", {})
    is_bank_statement = doc_analysis.get("is_bank_statement", False)
    
    print(f"\nDocument Type: {doc_analysis.get('document_type', 'Unknown')} (Confidence: {doc_analysis.get('confidence', 0):.2f})")
    
    if not is_bank_statement:
        print("\nThis document does not appear to be a bank statement.")
        print("Analysis aborted.")
        return
    
    # Business details
    business = analysis.get("business_details", {})
    print("\nBUSINESS SUMMARY:")
    print(f"Entity: {business.get('business_name', 'Not found')}")
    print(f"Bank: {business.get('bank_name', 'Not found')}")
    print(f"Statement Period: {business.get('statement_period', 'Not found')}")
    
    # Financial summary
    financial_data = analysis.get("financial_analysis", {}).get("financial_data", {})
    opening = financial_data.get('opening_balance', {})
    closing = financial_data.get('closing_balance', {})
    
    print("\nFINANCIAL SUMMARY:")
    print(f"Opening Balance: {opening.get('amount', 'Not found')} ({opening.get('date', 'No date')})")
    print(f"Closing Balance: {closing.get('amount', 'Not found')} ({closing.get('date', 'No date')})")
    print(f"Transaction Volume: {financial_data.get('transaction_count', 0)} transactions")
    
    # Risk assessment
    fraud = analysis.get("fraud_detection", {})
    fraud_risk = fraud.get("overall_risk", {})
    
    print("\nRISK ASSESSMENT:")
    risk_score = fraud_risk.get("risk_score", 0)
    risk_confidence = fraud_risk.get("confidence", 0)
    print(f"Risk Level: {fraud_risk.get('risk_level', 'Unknown')} (Score: {risk_score:.0%}, Confidence: {risk_confidence:.0%})")
    
    # Display component risk details
    if "component_details" in fraud_risk:
        print("\nRISK COMPONENT DETAILS:")
        components = fraud_risk.get("component_details", {})
        
        for component_name, details in components.items():
            risk_score = details.get("risk_score", 0)
            # Only show components with some risk
            if risk_score > 0:
                confidence = details.get("confidence", 0)
                print(f"\n  {component_name.replace('_', ' ').title()} Risk:")
                print(f"    Score: {risk_score:.2f} (Confidence: {confidence:.2f})")
                
                # Show a sample of evidence (first 3 items)
                evidence = details.get("evidence", [])
                if evidence:
                    print(f"    Key Evidence:")
                    for i, item in enumerate(evidence[:3]):  # Show first 3 pieces of evidence
                        print(f"      - {item}")
                    if len(evidence) > 3:
                        print(f"      - Plus {len(evidence) - 3} more evidence items...")
    
    # Consolidate all risk factors
    all_risk_factors = []
    
    # Add fraud risk factors
    if fraud_risk.get("risk_factors", []):
        all_risk_factors.extend(fraud_risk.get("risk_factors", []))
    
    # Add financial pattern risk factors (if not already included in risk_factors)
    suspicious = analysis.get("financial_analysis", {}).get("suspicious_patterns", {})
    if suspicious.get("suspicious_patterns_found", False) and not any("suspicious financial pattern" in factor.lower() for factor in all_risk_factors):
        all_risk_factors.extend(suspicious.get("suspicious_patterns", []))
    
    # Add reconciliation issues (if not already included in risk_factors)
    reconciliation = analysis.get("financial_analysis", {}).get("reconciliation", {})
    if reconciliation.get("reconciliation_possible", False) and not reconciliation.get("matches", True) and not any("balance discrepancy" in factor.lower() for factor in all_risk_factors):
        discrepancy = reconciliation.get("discrepancy", 0)
        all_risk_factors.append(f"Balance reconciliation failed: Discrepancy of {discrepancy}")
    
    # Display all risk factors
    if all_risk_factors:
        print("\nKey Risk Indicators:")
        for factor in all_risk_factors:
            print(f"  - {factor}")
    else:
        print("\nNo significant risk factors detected")
    
    # Verification summary 
    print("\nVERIFICATION SUMMARY:")
    
    if fraud_risk.get("risk_level") in ["Minimal", "Low"]:
        print("VERIFIED - Document appears to be authentic with low risk indicators")
    elif fraud_risk.get("risk_level") == "Medium":
        print("CAUTION - Document has medium risk indicators that warrant additional verification")
    else:  # High risk
        print("HIGH RISK - Document shows significant risk indicators; additional verification strongly recommended")
    
    print_section_header("END OF RISK PROFILE") 