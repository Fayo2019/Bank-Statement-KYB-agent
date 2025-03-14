from typing import Dict, Any

def assess_fraud_risk(visual_tampering: Dict[str, Any], 
                     structure_analysis: Dict[str, Any], 
                     financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """Assess overall fraud risk based on various signals with confidence scores and detailed evidence."""
    # Extract reconciliation and suspicious patterns from financial_data
    reconciliation = financial_data.get("reconciliation", {})
    suspicious_patterns = financial_data.get("suspicious_patterns", {})
    confidence = financial_data.get("confidence", 0.5)
    
    # Initialize component scores with evidence
    component_results = {
        "visual_tampering": {
            "risk_score": 0.0,
            "confidence": visual_tampering.get("confidence", 0.0),
            "evidence": []
        },
        "structure": {
            "risk_score": 0.0,
            "confidence": structure_analysis.get("confidence", 0.0),
            "evidence": structure_analysis.get("findings", [])
        },
        "reconciliation": {
            "risk_score": 0.0,
            "confidence": confidence,
            "evidence": []
        },
        "suspicious_patterns": {
            "risk_score": 0.0,
            "confidence": confidence,
            "evidence": suspicious_patterns.get("suspicious_patterns", [])
        }
    }
    
    # Visual tampering assessment
    if visual_tampering.get("tampering_detected", False):
        component_results["visual_tampering"]["risk_score"] = visual_tampering.get("confidence", 0)
        component_results["visual_tampering"]["evidence"] = visual_tampering.get("evidence", [])
        
        if visual_tampering.get("suspicious_areas"):
            suspicious_areas = visual_tampering.get("suspicious_areas", [])
            if isinstance(suspicious_areas, list):
                component_results["visual_tampering"]["evidence"].extend([
                    f"Suspicious area detected: {area}" for area in suspicious_areas
                ])
            else:
                component_results["visual_tampering"]["evidence"].append(f"Suspicious area: {suspicious_areas}")
    
    # Structure analysis assessment
    if structure_analysis.get("issues_detected", False):
        component_results["structure"]["risk_score"] = component_results["structure"]["confidence"]
        if structure_analysis.get("reasoning"):
            component_results["structure"]["evidence"].append(f"LLM reasoning: {structure_analysis.get('reasoning')}")
    
    # Reconciliation assessment
    if not reconciliation.get("matches", True):
        component_results["reconciliation"]["risk_score"] = component_results["reconciliation"]["confidence"]
        component_results["reconciliation"]["evidence"] = [
            f"Balance discrepancy of {reconciliation.get('discrepancy', 'unknown')} detected",
            f"Expected: {reconciliation.get('expected_closing_balance', 'unknown')}",
            f"Reported: {reconciliation.get('reported_closing_balance', 'unknown')}"
        ]
    elif "error" in reconciliation:
        component_results["reconciliation"]["risk_score"] = 0.3
        component_results["reconciliation"]["evidence"] = [
            f"Could not perform balance reconciliation: {reconciliation.get('error', 'Unknown reason')}"
        ]
    else:
        component_results["reconciliation"]["evidence"] = ["Balance reconciliation successful"]
    
    # Suspicious patterns assessment
    if suspicious_patterns.get("suspicious_patterns_found", False):
        component_results["suspicious_patterns"]["risk_score"] = component_results["suspicious_patterns"]["confidence"]
        
    # Calculate final risk score and confidence
    final_risk_score = min(1.0, sum(component["risk_score"] for component in component_results.values()))
    final_confidence = sum(c["confidence"] for c in component_results.values()) / len(component_results)
    
    # Determine risk level
    risk_level = "High" if final_risk_score >= 0.5 else "Medium" if final_risk_score >= 0.2 else "Low" if final_risk_score >= 0.05 else "Minimal"
    
    # Consolidate risk factors for the summary
    risk_factors = []
    for component_name, component_data in component_results.items():
        if component_data["risk_score"] > 0:
            # Add a summary for each risky component
            if component_name == "visual_tampering":
                confidence = component_data["confidence"]
                if confidence > 0.7:
                    risk_factors.append(f"HIGH CONFIDENCE visual tampering detected ({confidence:.2f})")
                elif confidence > 0.4:
                    risk_factors.append(f"Medium confidence visual tampering detected ({confidence:.2f})")
                else:
                    risk_factors.append(f"Possible visual tampering detected ({confidence:.2f})")
            
            elif component_name == "structure":
                findings_count = len(component_data["evidence"])
                risk_factors.append(f"PDF structure anomalies detected ({findings_count} issues)")
            
            elif component_name == "reconciliation" and "discrepancy" in reconciliation:
                risk_factors.append(f"Balance discrepancy detected: {reconciliation.get('discrepancy', 'unknown')}")
            
            elif component_name == "suspicious_patterns":
                # Add each suspicious pattern directly to risk factors instead of just a count
                for pattern in component_data["evidence"]:
                    risk_factors.append(f"Suspicious pattern: {pattern}")
    
    return {
        "risk_score": round(final_risk_score, 2),
        "risk_level": risk_level,
        "confidence": round(final_confidence, 2),
        "risk_factors": risk_factors,
        "component_details": {
            component: {
                "risk_score": round(data["risk_score"], 2),
                "confidence": round(data["confidence"], 2),
                "evidence": data["evidence"]
            } for component, data in component_results.items()
        }
    } 