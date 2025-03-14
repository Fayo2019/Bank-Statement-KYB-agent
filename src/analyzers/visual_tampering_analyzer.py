import os
from typing import Dict, List, Any
from src.utils.api_utils import get_completion

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