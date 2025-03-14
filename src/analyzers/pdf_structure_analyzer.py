import os
import json
from typing import Dict, Any
import pikepdf
from src.utils.api_utils import get_completion

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