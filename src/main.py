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
from typing import Dict, List, Tuple, Any, Optional, Union, Callable
import pikepdf
import time
import argparse

def encode_image(image) -> str:
    """Convert a PIL Image to base64 string."""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def call_openai_api(client: OpenAI, messages: List[Dict], model: str = "gpt-4o", json_mode: bool = False) -> Any:
    """Make a request to OpenAI's API with optional message input."""
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

def get_completion(prompt: str, images: List = None, model: str = "gpt-4o", json_mode: bool = False) -> Any:
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
    return call_openai_api(client, messages, model, json_mode)

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
    """Extract metadata from a PDF file."""
    info = {"Pages": 0, "Metadata Found": False}
    
    try:
        with pikepdf.open(pdf_path) as pdf:
            info = extract_pikepdf_metadata(pdf)
    except Exception as pikepdf_error:
        info = extract_pypdf_metadata(pdf_path, pikepdf_error)
    
    if not info.get("Metadata Found", False):
        print("Warning: No metadata found in the PDF file.")
        
    return info

def create_vision_prompt(template: str, images: List, model: str = "gpt-4o") -> Dict[str, Any]:
    """Create a vision prompt for the given template and images."""
    return get_completion(template, images, model=model, json_mode=True)

def analyze_document_type(images: List, model: str = "gpt-4o") -> Dict[str, Any]:
    """Analyze if the document is a bank statement."""
    prompt = """Analyze these document images and determine with high confidence if this is a business bank statement.
    Bank statements are a document that shows the transactions and balance of a business account containing the business's address, account number, bank name, bank logo, bank balance etc.

    If it is a bank statement, explain what elements confirm this (account numbers, transaction listings, bank name, transactions and balances not adding up etc.).
    If not, identify what type of document it appears to be.
    
    Return a JSON object with:
    - "is_bank_statement": boolean
    - "confidence": number between 0-1
    - "document_type": the identified document type
    - "evidence": key elements that support your classification
    - "bank_name": name of the bank if identifiable
    """
    return create_vision_prompt(prompt, images, model)

def extract_business_details(images: List, model: str = "gpt-4o") -> Dict[str, Any]:
    """Extract business name, address, account details from the document."""
    prompt = """Extract the following information from what appears to be a business bank statement:
    
    1. Business name
    2. Business address (complete with postal/zip code if available)
    3. Account number (last 4 digits only for security)
    4. Statement period (date range)
    5. Any business identifiers (like company registration numbers)
    
    Return the data in a JSON format with these fields. If any information is not found, mark it as "not found".
    """
    return create_vision_prompt(prompt, images, model)

def extract_financial_data(images: List, model: str = "gpt-4o") -> Dict[str, Any]:
    """Extract transaction data and balance information."""
    prompt = """Extract all financial information from this bank statement including:
    
    1. Opening balance with date
    2. Closing balance with date
    3. All transactions with:
       - Date
       - Description
       - Amount (negative for debits, positive for credits)
       - Running balance if available
    
    Return the data in a structured JSON with these categories. For transactions, return an array of transaction objects.
    If the document doesn't contain this information or appears incomplete, indicate this in your response.
    """
    return create_vision_prompt(prompt, images, model)

def parse_amount(amount_str: Union[str, float, int]) -> float:
    """Convert a string amount to a float, removing currency symbols."""
    if isinstance(amount_str, (int, float)):
        return float(amount_str)
    
    # Remove currency symbols and other non-numeric characters
    # Specifically handle £ (\u00a3), $ (dollar), € (euro), etc.
    cleaned_str = re.sub(r'[£$€¥₹\u00a3\u20AC\u00A5\u20B9]', '', str(amount_str))
    # Remove any remaining non-numeric characters except decimal point and negative sign
    cleaned_str = re.sub(r'[^\d.-]', '', cleaned_str)
    return float(cleaned_str)

def reconcile_balance(financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """Verify if the net change in transactions reconciles with statement balances."""
    try:
        opening_balance = financial_data.get('opening_balance', {}).get('amount')
        closing_balance = financial_data.get('closing_balance', {}).get('amount')
        transactions = financial_data.get('transactions', [])
        
        if opening_balance is None or closing_balance is None:
            return {
                "reconciliation_possible": False,
                "reason": "Missing opening or closing balance"
            }
            
        opening_balance = parse_amount(opening_balance)
        closing_balance = parse_amount(closing_balance)
        
        transaction_net_change = sum(parse_amount(t.get('amount', 0)) for t in transactions)
        expected_closing = opening_balance + transaction_net_change
        
        matches = abs(expected_closing - closing_balance) < 0.01
        
        return {
            "reconciliation_possible": True,
            "matches": matches,
            "opening_balance": opening_balance,
            "calculated_net_change": transaction_net_change,
            "expected_closing_balance": expected_closing,
            "reported_closing_balance": closing_balance,
            "discrepancy": closing_balance - expected_closing
        }
    except Exception as e:
        return {
            "reconciliation_possible": False,
            "reason": f"Error during reconciliation: {str(e)}"
        }

def detect_visual_tampering(images: List, model: str = "gpt-4o") -> Dict[str, Any]:
    """Detect visual signs of document tampering."""
    prompt = """
    Carefully analyze this document for any visual signs of tampering or falsification. Look for:
    
    1. Inconsistent fonts or formatting
    2. Misaligned text or tables
    3. Signs of text deletion or addition
    4. Unusual pixelation or artifacts around text
    5. Inconsistent spacing or background
    6. Placeholder text like "XXXX" or "[ENTER TEXT HERE]"
    
    Return your analysis as a JSON with:
    - "tampering_detected": boolean
    - "confidence": number between 0-1
    - "evidence": list of suspicious elements with descriptions
    - "suspicious_areas": locations in the document with potential issues
    """
    return create_vision_prompt(prompt, images, model)

def analyze_page_structure(page, page_num: int) -> List[str]:
    """Analyze a single page for potential structure issues."""
    findings = []
    
    if '/Resources' in page:
        resources = page['/Resources']
        
        if '/XObject' in resources and len(resources['/XObject']) > 20:
            findings.append(f"Page {page_num+1}: Unusually high number of embedded objects")
        
        if '/Font' in resources and isinstance(resources['/Font'], dict) and len(resources['/Font']) > 15:
            findings.append(f"Page {page_num+1}: Unusually high number of fonts")
    
    if '/Contents' in page:
        contents = page['/Contents']
        if isinstance(contents, list) and len(contents) > 5:
            findings.append(f"Page {page_num+1}: Multiple content streams detected (possible layered content)")
    
    if len(list(page.keys())) > 15:
        findings.append(f"Page {page_num+1}: Complex page structure detected")
    
    return findings

def check_modification_dates(pdf: pikepdf.Pdf) -> Optional[str]:
    """Check if the document has been modified after creation."""
    if pdf.trailer.get('/Info') and '/ModDate' in pdf.trailer['/Info']:
        mod_date = str(pdf.trailer['/Info']['/ModDate'])
        create_date = str(pdf.trailer['/Info'].get('/CreationDate', ''))
        if create_date and mod_date and mod_date != create_date:
            return "Document has been modified after creation"
    return None

def analyze_pdf_structure(pdf_path: str) -> Dict[str, Any]:
    """Analyze the PDF structure for hidden content, overlays, or other anomalies."""
    results = {
        "issues_detected": False,
        "findings": []
    }
    
    try:
        with pikepdf.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                findings = analyze_page_structure(page, page_num)
                if findings:
                    results["issues_detected"] = True
                    results["findings"].extend(findings)
            
            modification_finding = check_modification_dates(pdf)
            if modification_finding:
                results["findings"].append(modification_finding)
    
    except Exception as e:
        results["findings"].append(f"Error analyzing PDF structure: {str(e)}")
    
    return results

def assess_fraud_risk(visual_tampering: Dict[str, Any], 
                     structure_analysis: Dict[str, Any], 
                     reconciliation: Dict[str, Any]) -> Dict[str, Any]:
    """Assess overall fraud risk based on various signals by directly summing component scores capped at 1.0."""
    risk_factors = []
    
    # Calculate individual risk scores for each component
    visual_tampering_risk = 0.0
    structure_risk = 0.0
    reconciliation_risk = 0.0
    
    # Visual tampering risk score
    if visual_tampering.get("tampering_detected", False):
        confidence = visual_tampering.get("confidence", 0)
        visual_tampering_risk = confidence
        
        # Evidence description
        if confidence > 0.7:
            risk_factors.append(f"HIGH CONFIDENCE visual tampering detected ({confidence:.2f})")
        elif confidence > 0.4:
            risk_factors.append(f"Medium confidence visual tampering detected ({confidence:.2f})")
        else:
            risk_factors.append(f"Possible visual tampering detected ({confidence:.2f})")
    
    # PDF structure risk score
    if structure_analysis.get("issues_detected", False):
        findings_count = len(structure_analysis.get("findings", []))
        # Calculate structure risk based on number of findings (0.025 per finding)
        structure_risk = min(1.0, findings_count * 0.025)
        risk_factors.append(f"PDF structure anomalies detected ({findings_count} issues)")
    
    # Balance reconciliation risk score
    if reconciliation.get("reconciliation_possible", False) and not reconciliation.get("matches", True):
        discrepancy = abs(reconciliation.get("discrepancy", 0))
        reported_balance = abs(reconciliation.get("reported_closing_balance", 1))
        
        if reported_balance > 0:
            # Calculate reconciliation risk based on the discrepancy percentage
            reconciliation_risk = min(1.0, discrepancy / reported_balance)
            
            if reconciliation_risk > 0.1:
                risk_factors.append(f"SIGNIFICANT balance discrepancy: {reconciliation_risk:.2%} of total balance")
            else:
                risk_factors.append(f"Balance discrepancy: {reconciliation_risk:.2%} of total balance")
    
    # Calculate final risk score by summing the individual components
    # Cap at 1.0 if the sum exceeds 1.0
    risk_score = min(1.0, visual_tampering_risk + structure_risk + reconciliation_risk)
    
    # For reporting purposes, include the individual component scores
    component_scores = {
        "visual_tampering_risk": round(visual_tampering_risk, 2),
        "structure_risk": round(structure_risk, 2),
        "reconciliation_risk": round(reconciliation_risk, 2)
    }
    
    # Determine risk level with existing thresholds
    if risk_score >= 0.7:
        risk_level = "High"
    elif risk_score >= 0.4:
        risk_level = "Medium"
    elif risk_score >= 0.15:
        risk_level = "Low"
    else:
        risk_level = "Minimal"
    
    return {
        "risk_score": round(risk_score, 2),  # Round to 2 decimal places
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "component_scores": component_scores  # Include breakdown of component scores
    }

def analyze_bank_statement(pdf_path: str, model: str = "gpt-4o", verbose: bool = False) -> Dict[str, Any]:
    """Complete analysis of a bank statement PDF."""
    images = time_process("PDF to Images Conversion", pdf2image.convert_from_path, pdf_path, verbose=verbose)
    
    max_pages = min(len(images), 20)
    if len(images) > max_pages:
        images = images[:max_pages]
        if verbose:
            print(f"Limiting analysis to first {max_pages} pages")
    
    metadata = time_process("PDF Metadata Extraction", get_pdf_metadata, pdf_path, verbose=verbose)
    
    # Limit document type analysis to first 2 pages only
    doc_type_images = images[:min(2, len(images))]
    if verbose:
        print(f"Using only first {len(doc_type_images)} pages to determine if document is a bank statement")
    document_type = time_process("Document Type Analysis", analyze_document_type, doc_type_images, model=model, verbose=verbose)
    
    if not document_type.get("is_bank_statement", False):
        return {
            "document_analysis": {
                "is_bank_statement": False,
                "document_type": document_type.get("document_type", "Unknown"),
                "confidence": document_type.get("confidence", 0),
                "metadata": metadata
            }
        }
    
    # Continue with full analysis using all available pages
    business_details = time_process("Business Details Extraction", extract_business_details, images, model=model, verbose=verbose)
    financial_data = time_process("Financial Data Extraction", extract_financial_data, images, model=model, verbose=verbose)
    
    reconciliation = time_process("Balance Reconciliation", reconcile_balance, financial_data, verbose=verbose)
    visual_tampering = time_process("Visual Tampering Detection", detect_visual_tampering, images, model=model, verbose=verbose)
    structure_analysis = time_process("PDF Structure Analysis", analyze_pdf_structure, pdf_path, verbose=verbose)
    
    fraud_risk = time_process("Fraud Risk Assessment", assess_fraud_risk, visual_tampering, structure_analysis, reconciliation, verbose=verbose)
    
    return {
        "document_analysis": {
            "is_bank_statement": document_type.get("is_bank_statement", False),
            "document_type": document_type.get("document_type", "Unknown"),
            "confidence": document_type.get("confidence", 0),
            "bank_name": document_type.get("bank_name", "Unknown"),
            "metadata": metadata
        },
        "business_details": business_details,
        "financial_analysis": {
            "financial_data": financial_data,
            "reconciliation": reconciliation
        },
        "fraud_detection": {
            "visual_tampering": visual_tampering,
            "structure_analysis": structure_analysis,
            "overall_risk": fraud_risk
        }
    }

def print_section_header(title: str) -> None:
    """Print a section header."""
    print("\n" + "="*50)
    print(title)
    print("="*50)

def print_analysis_summary(analysis: Dict[str, Any]) -> None:
    """Print a human-readable summary of the analysis."""
    print_section_header("BANK STATEMENT VERIFICATION SUMMARY")
    
    doc_analysis = analysis.get("document_analysis", {})
    is_bank_statement = doc_analysis.get("is_bank_statement", False)
    
    print(f"\nDocument Type: {doc_analysis.get('document_type', 'Unknown')} (Confidence: {doc_analysis.get('confidence', 0):.2f})")
    
    if not is_bank_statement:
        print("\nThis document does not appear to be a bank statement.")
        print("Analysis aborted.")
        return
    
    # Business details
    business = analysis.get("business_details", {})
    print("\nBUSINESS DETAILS:")
    print(f"Name: {business.get('business_name', 'Not found')}")
    print(f"Address: {business.get('business_address', 'Not found')}")
    print(f"Account: {business.get('account_number', 'Not found')}")
    print(f"Statement Period: {business.get('statement_period', 'Not found')}")
    
    # Financial reconciliation
    reconciliation = analysis.get("financial_analysis", {}).get("reconciliation", {})
    print("\nFINANCIAL RECONCILIATION:")
    
    if reconciliation.get("reconciliation_possible", False):
        if reconciliation.get("matches", False):
            print("Balance reconciliation successful")
        else:
            print("Balance reconciliation failed")
            print(f"  Opening Balance: {reconciliation.get('opening_balance', 'N/A')}")
            print(f"  Net Transaction Change: {reconciliation.get('calculated_net_change', 'N/A')}")
            print(f"  Expected Closing Balance: {reconciliation.get('expected_closing_balance', 'N/A')}")
            print(f"  Reported Closing Balance: {reconciliation.get('reported_closing_balance', 'N/A')}")
            print(f"  Discrepancy: {reconciliation.get('discrepancy', 'N/A')}")
    else:
        print(f"Reconciliation not possible: {reconciliation.get('reason', 'Unknown reason')}")
    
    # Fraud detection
    fraud = analysis.get("fraud_detection", {})
    fraud_risk = fraud.get("overall_risk", {})
    
    print("\nFRAUD DETECTION:")
    risk_score = fraud_risk.get("risk_score", 0)
    print(f"Risk Level: {fraud_risk.get('risk_level', 'Unknown')} (Score: {risk_score:.0%})")  # Format as percentage
    
    if fraud_risk.get("risk_factors", []):
        print("Risk Factors:")
        for factor in fraud_risk.get("risk_factors", []):
            print(f"  - {factor}")
    
    visual = fraud.get("visual_tampering", {})
    if visual.get("tampering_detected", False):
        print("\nVisual Tampering Evidence:")
        for evidence in visual.get("evidence", []):
            print(f"  - {evidence}")
    
    structure = fraud.get("structure_analysis", {})
    if structure.get("issues_detected", False):
        print("\nPDF Structure Issues:")
        for finding in structure.get("findings", []):
            print(f"  - {finding}")
    
    print_section_header("END OF ANALYSIS")

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
            
        elif process_name == "Business Details Extraction" and isinstance(result, dict):
            print(f"Business Name: {result.get('business_name', 'Not found')}")
            print(f"Account Number: {result.get('account_number', 'Not found')}")
            
        elif process_name == "Financial Data Extraction" and isinstance(result, dict):
            opening = result.get('opening_balance', {})
            closing = result.get('closing_balance', {})
            transactions = result.get('transactions', [])
            print(f"Opening Balance: {opening.get('amount', 'Not found')} ({opening.get('date', 'No date')})")
            print(f"Closing Balance: {closing.get('amount', 'Not found')} ({closing.get('date', 'No date')})")
            print(f"Transactions Found: {len(transactions)}")
            
        elif process_name == "Balance Reconciliation" and isinstance(result, dict):
            if result.get("reconciliation_possible", False):
                print(f"Reconciliation Match: {result.get('matches', False)}")
                if not result.get('matches', True):
                    print(f"Discrepancy: {result.get('discrepancy', 'N/A')}")
            else:
                print(f"Reconciliation Not Possible: {result.get('reason', 'Unknown reason')}")
                
        elif process_name == "Visual Tampering Detection" and isinstance(result, dict):
            print(f"Tampering Detected: {result.get('tampering_detected', False)}")
            print(f"Confidence: {result.get('confidence', 0):.2f}")
            if result.get('evidence', []):
                print(f"Evidence found: {len(result.get('evidence', []))} items")
            
        elif process_name == "PDF Structure Analysis" and isinstance(result, dict):
            print(f"Issues Detected: {result.get('issues_detected', False)}")
            if result.get('findings', []):
                print(f"Found {len(result.get('findings', []))} issues")
                for finding in result.get('findings', [])[:3]:  # Show first 3 findings at most
                    print(f"  - {finding}")
                
        elif process_name == "Fraud Risk Assessment" and isinstance(result, dict):
            print(f"Risk Level: {result.get('risk_level', 'Unknown')}")
            print(f"Risk Score: {result.get('risk_score', 0):.2f}")
            if result.get('risk_factors', []):
                print("Risk Factors:")
                for factor in result.get('risk_factors', []):
                    print(f"  - {factor}")
            
        print()  # Extra empty line after each process
    
    return result

def main():
    """Main function to run the analysis."""
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables")
        sys.exit(1)
    
    # Set up command line arguments
    parser = argparse.ArgumentParser(description="Analyze a bank statement PDF for potential fraud.")
    parser.add_argument("pdf_path", help="Path to the PDF file to analyze")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output with timing information")
    parser.add_argument("-o", "--output", help="Path where the analysis report will be saved (default: alongside the PDF)")
    args = parser.parse_args()
    
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: File '{pdf_path}' does not exist")
        sys.exit(1)

    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    print(f"Analyzing document: {pdf_path} (using model: {model})")
    
    start_time = time.time()
    analysis = analyze_bank_statement(pdf_path, model=model, verbose=args.verbose)
    
    if args.verbose:
        total_time = time.time() - start_time
        print(f"\nTotal analysis time: {total_time:.2f} seconds")
    
    print_analysis_summary(analysis)
    
    # Determine output path - use custom path if provided, otherwise use default
    if args.output:
        output_path = Path(args.output)
        # Ensure output is a file path, not just a directory
        if output_path.is_dir():
            output_path = output_path / f"{pdf_path.stem}.analysis.json"
    else:
        output_path = pdf_path.with_suffix('.analysis.json')
    
    # Convert to JSON string
    json_str = json.dumps(analysis, indent=2)
    
    # Replace currency symbols in the JSON string
    json_str = json_str.replace('\\u00a3', '')  # Pound symbol
    json_str = json_str.replace('£', '')        # Direct pound symbol
    json_str = json_str.replace('$', '')        # Dollar symbol
    json_str = json_str.replace('€', '')        # Euro symbol
    json_str = json_str.replace('\\u20AC', '')  # Euro unicode
    
    # Write to file
    with open(output_path, 'w') as f:
        f.write(json_str)
    
    print(f"Detailed analysis saved to: {output_path}")

if __name__ == "__main__":
    main()