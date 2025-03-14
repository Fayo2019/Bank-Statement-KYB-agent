import re
from typing import Union

def parse_amount(amount_str: Union[str, float, int]) -> float:
    """Convert a string amount to a float, removing currency symbols."""
    if isinstance(amount_str, (int, float)):
        return float(amount_str)
    
    # Remove currency symbols and other non-numeric characters
    cleaned_str = re.sub(r'[£$€¥₹\u00a3\u20AC\u00A5\u20B9]', '', str(amount_str))
    # Remove any remaining non-numeric characters except decimal point and negative sign
    cleaned_str = re.sub(r'[^\d.-]', '', cleaned_str)
    
    return float(cleaned_str)

def print_section_header(title: str) -> None:
    """Print a section header."""
    print("\n" + "="*50)
    print(title)
    print("="*50) 