import pdf2image
import base64
from io import BytesIO
from typing import List

def encode_image(image) -> str:
    """Convert a PIL Image to base64 string."""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def convert_pdf_to_images(pdf_path: str) -> List:
    """Convert a PDF file to a list of PIL Images."""
    return pdf2image.convert_from_path(pdf_path) 