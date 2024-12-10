# core/data_cleaner.py
import re
from typing import Dict, Any

class DataCleaner:
    @staticmethod
    def clean_price(price: str) -> float:
        try:
            return float(re.sub(r'[^\d.]', '', price))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def clean_processor_info(processor_info: str) -> Dict[str, str]:
        info = {
            "brand": "",
            "model": "",
            "generation": ""
        }
        
        # Extract processor brand
        brands = ["Intel", "AMD", "Apple"]
        for brand in brands:
            if brand.lower() in processor_info.lower():
                info["brand"] = brand
                break

        # Extract generation (Intel)
        gen_match = re.search(r'(\d+)th Gen', processor_info)
        if gen_match:
            info["generation"] = f"{gen_match.group(1)}th Gen"

        # Extract model
        models = {
            "i3": "Core i3",
            "i5": "Core i5",
            "i7": "Core i7",
            "i9": "Core i9",
            "ryzen": "Ryzen"
        }
        for key, value in models.items():
            if key.lower() in processor_info.lower():
                info["model"] = value
                break

        return info

    @staticmethod
    def clean_ram_info(ram_info: str) -> Dict[str, str]:
        info = {
            "size": "",
            "type": ""
        }
        
        # Extract RAM size
        size_match = re.search(r'(\d+)\s*GB', ram_info)
        if size_match:
            info["size"] = f"{size_match.group(1)}GB"

        # Extract RAM type
        types = ["DDR4", "DDR5", "LPDDR4", "LPDDR5"]
        for ram_type in types:
            if ram_type in ram_info:
                info["type"] = ram_type
                break

        return info

    @staticmethod
    def clean_storage_info(storage_info: str) -> Dict[str, str]:
        info = {
            "type": "",
            "capacity": ""
        }
        
        # Extract storage type
        types = ["SSD", "HDD", "eMMC"]
        for storage_type in types:
            if storage_type in storage_info:
                info["type"] = storage_type
                break

        # Extract capacity
        capacity_match = re.search(r'(\d+)\s*(GB|TB)', storage_info)
        if capacity_match:
            info["capacity"] = f"{capacity_match.group(1)}{capacity_match.group(2)}"

        return info