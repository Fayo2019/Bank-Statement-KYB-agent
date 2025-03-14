import os
from typing import Dict, List, Any
from src.utils.api_utils import get_completion

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