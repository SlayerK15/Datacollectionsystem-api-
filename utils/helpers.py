# utils/helpers.py
import re
from typing import Dict, Any
from urllib.parse import urlparse

def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    return urlparse(url).netloc

def clean_text(text: str) -> str:
    """Remove special characters and extra whitespace."""
    return re.sub(r'\s+', ' ', text).strip()

def parse_price(price_str: str) -> float:
    """Convert price string to float."""
    try:
        return float(re.sub(r'[^\d.]', '', price_str))
    except (ValueError, TypeError):
        return 0.0

def merge_specs(old_specs: Dict[str, Any], new_specs: Dict[str, Any]) -> Dict[str, Any]:
    """Merge old and new specifications, keeping the most detailed information."""
    merged = old_specs.copy()
    for key, value in new_specs.items():
        if isinstance(value, dict):
            if key in merged:
                merged[key] = merge_specs(merged[key], value)
            else:
                merged[key] = value
        elif value:  # Only update if new value is not empty
            merged[key] = value
    return merged
