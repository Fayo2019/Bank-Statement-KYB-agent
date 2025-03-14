from typing import Dict, Any
import pikepdf
from PyPDF2 import PdfReader

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