from dotenv import load_dotenv
import pdf2image
import sys
from pathlib import Path
import os
from openai import OpenAI
import base64
from io import BytesIO
from PyPDF2 import PdfReader
import json
import re
from typing import Dict, List, Any, Union, Callable
import pikepdf
import time
import argparse

def encode_image(image) -> str:
    """Convert a PIL Image to base64 string."""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_completion(prompt: str, images: List = None, model: str = os.getenv("OPENAI_MODEL", "gpt-4o"), json_mode: bool = False) -> Any:
    """Make a request to OpenAI's API with optional image input."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
        
    client = OpenAI(api_key=api_key)
    images = images or []
    
    content = [{"type": "text", "text": prompt}]
    for img in images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{encode_image(img)}"
            }
        })
    
    messages = [{"role": "user", "content": content}]
    
    try:
        response_format = {"type": "json_object"} if json_mode else None
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4000,
            response_format=response_format
        )
        content = response.choices[0].message.content
        return json.loads(content) if json_mode else content
    except Exception as e:
        print(f"Error making OpenAI API request: {e}")
        return None

def extract_pikepdf_metadata(pdf: pikepdf.Pdf) -> Dict[str, Any]:
    """Extract metadata from a PDF file using pikepdf."""
    info = {"Pages": len(pdf.pages), "Metadata Found": False}
    
    if pdf.trailer.get('/Info'):
        metadata_dict = pdf.trailer['/Info']
        for key, value in metadata_dict.items():
            clean_key = str(key).replace('/', '')
            info[clean_key] = str(value)
        
        standard_fields = ["Title", "Author", "Creator", "Producer", "CreationDate", "ModDate"]
        for field in standard_fields:
            info.setdefault(field, "Not available")
            
        info["Metadata Found"] = True
    
    if pdf.Root.get('/Metadata'):
        info["XMP Metadata"] = "Present"
        info["Metadata Found"] = True
        
    return info

def extract_pypdf_metadata(pdf_path: str, pikepdf_error: Exception) -> Dict[str, Any]:
    """Extract metadata from a PDF file using PyPDF2 as a fallback."""
    try:
        reader = PdfReader(pdf_path)
        info = {"Pages": len(reader.pages), "Extraction Method": "PyPDF2 (fallback)", "PikePDF Error": str(pikepdf_error)}
        
        if reader.metadata:
            for key, value in reader.metadata.items():
                clean_key = str(key).replace('/', '')
                info[clean_key] = str(value)
            
            standard_fields = ["Title", "Author", "Creator", "Producer", "CreationDate", "ModDate"]
            for field in standard_fields:
                info.setdefault(field, "Not available")
                
            info["Metadata Found"] = True
        return info
    except Exception as pypdf_error:
        return {
            "Pages": 0, 
            "Metadata Found": False,
            "Metadata Extraction Error": f"PikePDF: {pikepdf_error}, PyPDF2: {pypdf_error}"
        }

def get_pdf_metadata(pdf_path: str) -> Dict[str, Any]:
    """Extract metadata from a PDF file using pikepdf with PyPDF2 as fallback."""
    info = {"Pages": 0, "Metadata Found": False}
    standard_fields = ["Title", "Author", "Creator", "Producer", "CreationDate", "ModDate"]
    
    # Try pikepdf first
    try:
        with pikepdf.open(pdf_path) as pdf:
            info["Pages"] = len(pdf.pages)
            
            if pdf.trailer.get('/Info'):
                metadata_dict = pdf.trailer['/Info']
                for key, value in metadata_dict.items():
                    clean_key = str(key).replace('/', '')
                    info[clean_key] = str(value)
                info["Metadata Found"] = True
            
            if pdf.Root.get('/Metadata'):
                info["XMP Metadata"] = "Present"
                info["Metadata Found"] = True
            
            # Return early if successful
            if info["Metadata Found"]:
                # Ensure standard fields exist
                for field in standard_fields:
                    info.setdefault(field, "Not available")
                return info
                
    except Exception as pikepdf_error:
        info["PikePDF Error"] = str(pikepdf_error)
    
    # Fall back to PyPDF2 if pikepdf failed or found no metadata
    try:
        reader = PdfReader(pdf_path)
        info["Pages"] = len(reader.pages)
        info["Extraction Method"] = "PyPDF2 (fallback)"
        
        if reader.metadata:
            for key, value in reader.metadata.items():
                clean_key = str(key).replace('/', '')
                info[clean_key] = str(value)
            info["Metadata Found"] = True
    except Exception as pypdf_error:
        info["PyPDF2 Error"] = str(pypdf_error)
    
    # Ensure standard fields exist
    for field in standard_fields:
        info.setdefault(field, "Not available")
    
    if not info.get("Metadata Found", False):
        print("Warning: No metadata found in the PDF file.")
        
    return info

def analyze_document_type(images: List, model: str = os.getenv("OPENAI_MODEL", "gpt-4o")) -> Dict[str, Any]:
    """Analyze if the document is a bank statement."""
    prompt = """Analyze these document images and determine with high confidence if this is a business bank statement.
    Bank statements are a document that shows the transactions and balance of a business account containing the business's address, account number, bank name, bank logo, bank balance etc.
    
    If it is a bank statement, provide detailed conclusive reasoning explaining what specific elements confirm this classification.
    Consider account numbers, transaction listings, bank name, bank logos, heading formats, transaction details, balance information, etc.
    
    If it is NOT a bank statement, provide detailed reasoning identifying what type of document it appears to be and why.
    
    Return a JSON object with:
    - "is_bank_statement": boolean
    - "confidence": number between 0-1
    - "document_type": the identified document type
    - "evidence": detailed reasoning explaining why you classified the document as this type, providing specific examples from the document
    - "bank_name": name of the bank if identifiable
    """
    return get_completion(prompt, images, model=model, json_mode=True)

def extract_business_details(images: List, model: str = os.getenv("OPENAI_MODEL", "gpt-4o")) -> Dict[str, Any]:
    """Extract business name, address, account details from the document."""
    prompt = """Extract the following information from what appears to be a business bank statement:
    
    1. Business name
    2. Business address (complete with postal/zip code if available)
    3. Bank/financial institution name
    4. Account number (last 4 digits only for security)
    5. Statement period (date range)
    6. Any business identifiers (like company registration numbers)
    
    Return the data in a JSON format with these fields. If any information is not found, mark it as "not found".
    """
    return get_completion(prompt, images, model=model, json_mode=True)

def parse_amount(amount_str: Union[str, float, int]) -> float:
    """Convert a string amount to a float, removing currency symbols."""
    if isinstance(amount_str, (int, float)):
        return float(amount_str)
    
    # Remove currency symbols and other non-numeric characters
    cleaned_str = re.sub(r'[£$€¥₹\u00a3\u20AC\u00A5\u20B9]', '', str(amount_str))
    # Remove any remaining non-numeric characters except decimal point and negative sign
    cleaned_str = re.sub(r'[^\d.-]', '', cleaned_str)
    return float(cleaned_str)

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

def detect_visual_tampering(images: List, model: str = os.getenv("OPENAI_MODEL", "gpt-4o")) -> Dict[str, Any]:
    """Detect visual signs of document tampering."""
    prompt = """
    Carefully analyze this document for any visual signs of tampering or falsification. Look for:
    
    1. Inconsistent fonts or formatting
    2. Misaligned text or tables
    3. Signs of text deletion or addition
    4. Unusual pixelation or artifacts around text
    5. Inconsistent spacing or background
    6. Missing necessary information (e.g. the bank's logo)
    7. Placeholder text like "XXXX" or "[ENTER TEXT HERE]". This be in the account numbers, transaction amounts etc.
    
    Return your analysis as a JSON with:
    - "tampering_detected": boolean
    - "confidence": number between 0-1 representing how confident you are there's been visual tampering.
    - "evidence": list of the specific suspicious elements with descriptions
    - "suspicious_areas": locations in the document with potential issues
    """
    return get_completion(prompt, images, model=model, json_mode=True)

def analyze_pdf_structure(pdf_path: str, model: str = os.getenv("OPENAI_MODEL", "gpt-4o")) -> Dict[str, Any]:
    """Analyze the PDF structure using an LLM for advanced pattern detection."""
    structure_data = {}
    
    try:
        with pikepdf.open(pdf_path) as pdf:
            # Extract core structural metadata concisely
            structure_data = {
                "page_count": len(pdf.pages),
                "version": str(pdf.pdf_version),
                "is_encrypted": pdf.is_encrypted,
                "has_javascript": "/JavaScript" in pdf.Root or "/JS" in pdf.Root,
                "has_embedded_files": "/Names" in pdf.Root and "/EmbeddedFiles" in pdf.Root["/Names"],
                "acroform_present": "/AcroForm" in pdf.Root,
                "info": {k.replace('/', ''): str(v) for k, v in pdf.trailer.get('/Info', {}).items()} if pdf.trailer.get('/Info') else {},
                "modification_history": {
                    "modified_after_creation": False
                },
                "page_analysis": {
                    "multiple_content_streams_count": 0,
                    "complex_pages_count": 0,
                    "total_fonts": 0,
                    "total_xobjects": 0,
                    "total_annotations": 0
                }
            }
            
            # Check creation vs modification dates
            info = pdf.trailer.get('/Info', {})
            if "/ModDate" in info and "/CreationDate" in info:
                mod_date = str(info["/ModDate"])
                create_date = str(info["/CreationDate"])
                structure_data["modification_history"]["modified_after_creation"] = mod_date != create_date
                structure_data["modification_history"]["creation_date"] = create_date
                structure_data["modification_history"]["mod_date"] = mod_date
            
            # Analyze page structure concisely
            for page in pdf.pages:
                # Content streams check
                if "/Contents" in page and isinstance(page["/Contents"], list) and len(page["/Contents"]) > 1:
                    structure_data["page_analysis"]["multiple_content_streams_count"] += 1
                
                # Complex page check
                if len(list(page.keys())) > 5:
                    structure_data["page_analysis"]["complex_pages_count"] += 1
                
                # Resource checks
                if "/Resources" in page:
                    res = page["/Resources"]
                    if "/Font" in res and isinstance(res["/Font"], dict):
                        structure_data["page_analysis"]["total_fonts"] += len(res["/Font"])
                    if "/XObject" in res and isinstance(res["/XObject"], dict):
                        structure_data["page_analysis"]["total_xobjects"] += len(res["/XObject"])
                
                # Annotations check
                if "/Annots" in page and isinstance(page["/Annots"], list):
                    structure_data["page_analysis"]["total_annotations"] += len(page["/Annots"])
    
    except Exception as e:
        return {
            "issues_detected": True,
            "confidence": 0.3,
            "findings": [f"Error analyzing PDF structure: {str(e)}"]
        }
    
    # Analyze with LLM
    prompt = """As a PDF forensic expert, analyze this document structure for signs of tampering:
    1. Multiple content streams often indicate layering to hide/overlay content
    2. Modification dates different from creation dates suggest editing
    3. Suspicious combinations of metadata
    4. Inconsistent document structure
    5. JavaScript or embedded files are unusual in legitimate financial documents
    6. Abnormal object counts (XObjects) may indicate manipulation
    7. Font inconsistencies may indicate manipulation
    8. Any patterns known to be associated with document forgery
    
    Return a JSON with:
    - "issues_detected": boolean
    - "confidence": number 0-1 (how confident you are tampering exists)
    - "findings": list of suspicious elements
    - "reasoning": brief but specific explanation of your assessment."""
    
    # Get LLM analysis
    analysis = get_completion(f"{prompt}\n\nPDF STRUCTURE DATA:\n{json.dumps(structure_data, indent=2)}", 
                             model=model, json_mode=True)
    
    return {
        "issues_detected": analysis.get("issues_detected", False),
        "confidence": analysis.get("confidence"),
        "findings": analysis.get("findings", []),
        "reasoning": analysis.get("reasoning", "No reasoning provided"),
        "llm_analysis": True
    }

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

def analyze_bank_statement(pdf_path: str, model: str = os.getenv("OPENAI_MODEL", "gpt-4o"), verbose: bool = False) -> Dict[str, Any]:
    """Complete analysis of a bank statement PDF."""
    # Convert PDF to images
    images = time_process("PDF to Images Conversion", pdf2image.convert_from_path, pdf_path, verbose=verbose)
    
    # Limit to first 20 pages for performance
    max_pages = min(len(images), 20)
    if len(images) > max_pages:
        images = images[:max_pages]
        if verbose:
            print(f"Limiting analysis to first {max_pages} pages")
    
    # Extract PDF metadata 
    metadata = time_process("PDF Metadata Extraction", get_pdf_metadata, pdf_path, verbose=verbose)
    
    # Check if it's a bank statement (using only first 2 pages for efficiency)
    document_type = time_process("Document Type Analysis", 
                                analyze_document_type, 
                                images[:min(2, len(images))], 
                                model=model, 
                                verbose=verbose)
    
    # Basic document analysis response structure
    result = {
        "document_analysis": {
            "is_bank_statement": document_type.get("is_bank_statement", False),
            "document_type": document_type.get("document_type", "Unknown"),
            "confidence": document_type.get("confidence", 0),
            "evidence": document_type.get("evidence", []),
            "metadata": metadata
        },
        "business_details": {
            "bank_name": document_type.get("bank_name", "Unknown")
        }
    }
    
    # If not a bank statement, return minimal analysis
    if not document_type.get("is_bank_statement", False):
        return result
    
    # Continue with full analysis on all available pages
    business_details = time_process("Business Details Extraction", 
                                   extract_business_details, 
                                   images, 
                                   model=model, 
                                   verbose=verbose)
    
    financial_data = time_process("Financial Data Extraction", 
                                 extract_financial_data, 
                                 images, 
                                 model=model, 
                                 verbose=verbose)
    
    visual_tampering = time_process("Visual Tampering Detection", 
                                   detect_visual_tampering, 
                                   images, 
                                   model=model, 
                                   verbose=verbose)
    
    structure_analysis = time_process("PDF Structure Analysis", 
                                     analyze_pdf_structure, 
                                     pdf_path, 
                                     model=model, 
                                     verbose=verbose)
    
    fraud_risk = time_process("Fraud Risk Assessment", 
                             assess_fraud_risk, 
                             visual_tampering, 
                             structure_analysis, 
                             financial_data, 
                             verbose=verbose)
    
    # If bank_name from document_type isn't already in business_details, add it
    if "bank_name" not in business_details and document_type.get("bank_name"):
        business_details["bank_name"] = document_type.get("bank_name")
    
    # Remove internal transaction data before adding to output
    if "_transactions_for_analysis" in financial_data:
        del financial_data["_transactions_for_analysis"]
    
    # Update the result with all analysis data
    result.update({
        "business_details": business_details,
        "fraud_detection": {
            "visual_tampering": visual_tampering,
            "structure_analysis": structure_analysis,
            "overall_risk": fraud_risk
        }
    })
    
    return result

def print_section_header(title: str) -> None:
    """Print a section header."""
    print("\n" + "="*50)
    print(title)
    print("="*50)

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

def main():
    """Main function to run the analysis."""
    load_dotenv()
    
    # Set up command line arguments
    parser = argparse.ArgumentParser(description="Analyze a bank statement PDF for potential fraud.")
    parser.add_argument("pdf_path", help="Path to the PDF file to analyze")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output with timing information")
    parser.add_argument("-o", "--output", help="Path where the analysis report will be saved (default: alongside the PDF)")
    args = parser.parse_args()
    
    # Validate inputs
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables")
        sys.exit(1)
    
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: File '{pdf_path}' does not exist")
        sys.exit(1)

    # Run analysis
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    print(f"Analyzing document: {pdf_path} (using model: {model})")
    
    start_time = time.time()
    analysis = analyze_bank_statement(pdf_path, model=model, verbose=args.verbose)
    
    if args.verbose:
        total_time = time.time() - start_time
        print(f"\nTotal analysis time: {total_time:.2f} seconds")
    
    # Print summary
    print_analysis_summary(analysis)
    
    # Save detailed results
    output_path = args.output if args.output else pdf_path.with_suffix('.analysis.json')
    output_path = Path(output_path)
    if output_path.is_dir():
        output_path = output_path / f"{pdf_path.stem}.analysis.json"
    
    # Convert to JSON string and clean currency symbols
    json_str = json.dumps(analysis, indent=2)
    for symbol in ['\\u00a3', '£', '$', '€', '\\u20AC']:
        json_str = json_str.replace(symbol, '')
    
    # Write to file
    with open(output_path, 'w') as f:
        f.write(json_str)
    
    print(f"Detailed analysis saved to: {output_path}")

if __name__ == "__main__":
    main()