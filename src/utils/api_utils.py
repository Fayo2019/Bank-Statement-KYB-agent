import os
import json
from typing import Dict, List, Any, Union
from openai import OpenAI
from .image_utils import encode_image

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