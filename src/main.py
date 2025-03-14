from dotenv import load_dotenv
import sys
from pathlib import Path
import os
import json
import time
import argparse

# Fix Python path for direct script execution
if __name__ == "__main__":
    # Add parent directory to Python path when run directly
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

# Import utility modules
from src.utils.timing import time_process
from src.utils.image_utils import convert_pdf_to_images
# Import extractor modules
from src.extractors.metadata_extractor import get_pdf_metadata
from src.extractors.document_type_extractor import analyze_document_type
from src.extractors.business_details_extractor import extract_business_details
from src.extractors.financial_data_extractor import extract_financial_data
# Import analyzer modules
from src.analyzers.visual_tampering_analyzer import detect_visual_tampering
from src.analyzers.pdf_structure_analyzer import analyze_pdf_structure
from src.analyzers.fraud_risk_analyzer import assess_fraud_risk
# Import output modules
from src.output.report_generator import print_analysis_summary

def analyze_bank_statement(pdf_path: str, model: str = os.getenv("OPENAI_MODEL", "gpt-4o"), verbose: bool = False) -> dict:
    """Complete analysis of a bank statement PDF."""
    # Convert PDF to images
    images = time_process("PDF to Images Conversion", convert_pdf_to_images, pdf_path, verbose=verbose)
    
    # Limit to first 20 pages for performance and cost limiting
    max_pages = min(len(images), 20)
    if len(images) > max_pages:
        images = images[:max_pages]
        if verbose:
            print(f"Limiting analysis to first {max_pages} pages")
    
    # Extract PDF metadata 
    metadata = time_process("PDF Metadata Extraction", get_pdf_metadata, pdf_path, verbose=verbose)
    
    # Check if it's a bank statement (using only first 2 pages for efficiency/cost)
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