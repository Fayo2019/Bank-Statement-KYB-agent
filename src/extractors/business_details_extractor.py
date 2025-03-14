import os
from typing import Dict, List, Any
from src.utils.api_utils import get_completion

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