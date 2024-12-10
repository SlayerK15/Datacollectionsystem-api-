# spiders/amazon_spider.py
from .base_spider import BaseSpider
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
import re
from datetime import datetime
import logging
from database.models import Laptop, LaptopSpecs

class AmazonSpider(BaseSpider):
    def __init__(self, session, rate_limiter, proxy_manager):
        super().__init__(session, rate_limiter, proxy_manager)
        self.base_url = "https://www.amazon.in/s?k=laptops"
        self.logger = logging.getLogger(self.__class__.__name__)

    async def extract_product_links(self, url: str) -> List[str]:
        """Extract product URLs from Amazon search results page."""
        try:
            content = await self.get_page_content(url)
            soup = BeautifulSoup(content, 'html.parser')
            links = []
            
            # Product grid items
            for item in soup.select('div[data-asin]'):
                asin = item.get('data-asin')
                if asin and asin.strip():
                    full_url = f"https://www.amazon.in/dp/{asin}"
                    links.append(full_url)
            
            self.logger.info(f"Extracted {len(links)} product links")
            return links[:10]  # Limit for testing
        except Exception as e:
            self.logger.error(f"Error extracting product links: {str(e)}", exc_info=True)
            return []

    async def extract_product_data(self, url: str) -> Optional[Laptop]:
        """Extract detailed product information from a product page."""
        try:
            content = await self.get_page_content(url)
            soup = BeautifulSoup(content, 'html.parser')
            self.logger.debug(f"Successfully fetched content for {url}")

            # Extract basic information
            title = self._extract_title(soup)
            if not title:
                self.logger.error(f"Could not find title for {url}")
                return None

            # Extract prices
            current_price = self._extract_current_price(soup)
            original_price = self._extract_original_price(soup) or current_price

            # Extract ratings
            ratings_count, average_rating = self._extract_ratings(soup)

            # Extract technical specifications
            tech_specs = self._extract_technical_specs(soup)
            
            # Create Laptop object
            laptop = Laptop(
                product_id=url.split('/dp/')[-1].split('/')[0],
                source="Amazon",
                url=url,
                title=title,
                brand=self._extract_brand(title, tech_specs),
                model=tech_specs.get('model_number', ''),
                current_price=current_price,
                original_price=original_price,
                ratings_count=ratings_count,
                average_rating=average_rating,
                specifications=self._create_laptop_specs(tech_specs),
                last_updated=datetime.utcnow()
            )

            self.logger.debug(f"Successfully created laptop object for {url}")
            return laptop

        except Exception as e:
            self.logger.error(f"Error extracting product data from {url}: {str(e)}", exc_info=True)
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract product title."""
        title_elem = soup.select_one('#productTitle')
        return self._clean_text(title_elem.text) if title_elem else ''

    def _extract_current_price(self, soup: BeautifulSoup) -> float:
        """Extract current price with multiple selector fallbacks."""
        price_selectors = [
            'span.a-price-whole',
            '.a-price .a-offscreen',
            '#priceblock_ourprice',
            '#priceblock_dealprice',
            '.apexPriceToPay .a-offscreen'
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                return self._extract_price(price_elem.text)
        return 0.0

    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract original price with multiple selector fallbacks."""
        price_selectors = [
            '.a-text-strike',
            '#priceblock_listprice',
            '.priceBlockStrikePriceString',
            '.a-price.a-text-price span[aria-hidden="true"]'
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                return self._extract_price(price_elem.text)
        return None

    def _extract_ratings(self, soup: BeautifulSoup) -> tuple[int, float]:
        """Extract ratings count and average rating."""
        try:
            # Extract ratings count
            ratings_count = 0
            ratings_elem = soup.select_one('#acrCustomerReviewText')
            if ratings_elem:
                ratings_count = int(re.sub(r'[^\d]', '', ratings_elem.text))

            # Extract average rating
            average_rating = 0.0
            rating_selectors = [
                '#averageCustomerReviews .a-icon-star',
                'i.a-icon-star .a-icon-alt',
                '[data-hook="rating-out-of-text"]'
            ]
            
            for selector in rating_selectors:
                rating_elem = soup.select_one(selector)
                if rating_elem:
                    rating_text = rating_elem.text.split()[0]
                    if rating_text:
                        average_rating = float(rating_text)
                        break

            return ratings_count, average_rating
        except (ValueError, AttributeError) as e:
            self.logger.warning(f"Error extracting ratings: {str(e)}")
            return 0, 0.0

    def _extract_technical_specs(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract all technical specifications from various sections."""
        specs = {}
        
        # Look in all possible spec locations
        spec_sections = [
            'div#productDetails_expanderSectionTables div.a-section table',
            'div#productDetails_techSpec_section_1',
            'div#productDetails_detailBullets_sections1',
            'div.a-expander-content table.prodDetTable'  # Expanded content tables
        ]
        
        # Extract from main spec tables
        for selector in spec_sections:
            tables = soup.select(selector)
            for table in tables:
                rows = table.select('tr')
                for row in rows:
                    label_elem = row.select_one('th')
                    value_elem = row.select_one('td')
                    if label_elem and value_elem:
                        label = self._clean_text(label_elem.text)
                        value = self._clean_text(value_elem.text)
                        if label and value:
                            key = label.lower().replace(' ', '_')
                            specs[key] = value
                            self.logger.debug(f"Found spec: {key} = {value}")

        # Process expandable sections
        expandable_sections = soup.select('div.a-expander-content')
        for section in expandable_sections:
            section_title = section.find_previous('span', class_='a-expander-prompt')
            if section_title:
                title = self._clean_text(section_title.text).lower()
                
                # Process based on section type
                if 'processor' in title:
                    self._extract_processor_section(section, specs)
                elif 'memory' in title:
                    self._extract_memory_section(section, specs)
                elif 'storage' in title or 'hard' in title:
                    self._extract_storage_section(section, specs)
                elif 'display' in title:
                    self._extract_display_section(section, specs)
                elif 'graphics' in title:
                    self._extract_graphics_section(section, specs)

        return specs
    
    def _create_laptop_specs(self, tech_specs: Dict[str, str]) -> LaptopSpecs:
        """Create LaptopSpecs object from extracted specifications."""
        try:
            return LaptopSpecs(
                processor=self._extract_processor_info(tech_specs),
                ram=self._extract_ram_info(tech_specs),
                storage=self._extract_storage_info(tech_specs),
                display=self._extract_display_info(tech_specs),
                graphics=self._extract_graphics_info(tech_specs),
                os=tech_specs.get('operating_system', ''),
                battery=self._extract_battery_info(tech_specs),
                ports=self._extract_ports_info(tech_specs),
                dimensions=self._extract_dimensions_info(tech_specs),
                additional_features=self._extract_additional_features(tech_specs)
            )
        except Exception as e:
            self.logger.error(f"Error creating laptop specs: {str(e)}")
            return LaptopSpecs()  # Return empty specs if there's an error

    def _extract_processor_section(self, section: BeautifulSoup, specs: Dict[str, str]):
        """Extract detailed processor information."""
        processor_selectors = [
            'td:-soup-contains("Processor")',
            'td:-soup-contains("CPU")',
            'td:-soup-contains("Processor Type")'
        ]
        
        for selector in processor_selectors:
            elem = section.select_one(selector)
            if elem:
                processor_info = self._clean_text(elem.text)
                specs['processor'] = processor_info
                specs['processor_type'] = processor_info
                specs['cpu_model'] = processor_info
                break

    def _extract_memory_section(self, section: BeautifulSoup, specs: Dict[str, str]):
        """Extract detailed memory information."""
        # RAM size
        ram_size = section.select_one('td:-soup-contains("GB")')
        if ram_size:
            specs['ram'] = self._clean_text(ram_size.text)
        
        # RAM type
        ram_type = section.select_one('td:-soup-contains("DDR")')
        if ram_type:
            specs['ram_type'] = self._clean_text(ram_type.text)
        
        # RAM speed
        ram_speed = section.select_one('td:-soup-contains("MHz")')
        if ram_speed:
            specs['memory_speed'] = self._clean_text(ram_speed.text)

    def _extract_storage_section(self, section: BeautifulSoup, specs: Dict[str, str]):
        """Extract detailed storage information."""
        storage_selectors = [
            'td:-soup-contains("SSD")',
            'td:-soup-contains("HDD")',
            'td:-soup-contains("Storage")',
            'td:-soup-contains("Hard Drive")'
        ]
        
        for selector in storage_selectors:
            elem = section.select_one(selector)
            if elem:
                storage_info = self._clean_text(elem.text)
                specs['storage'] = storage_info
                specs['hard_drive'] = storage_info
                break

    def _extract_display_section(self, section: BeautifulSoup, specs: Dict[str, str]):
        """Extract detailed display information."""
        # Display size
        size_elem = section.select_one('td:-soup-contains("inches")')
        if size_elem:
            specs['screen_size'] = self._clean_text(size_elem.text)
        
        # Resolution
        resolution_elem = section.select_one('td:-soup-contains("x")')
        if resolution_elem:
            specs['resolution'] = self._clean_text(resolution_elem.text)
        
        # Refresh rate
        refresh_elem = section.select_one('td:-soup-contains("Hz")')
        if refresh_elem:
            specs['refresh_rate'] = self._clean_text(refresh_elem.text)

    def _extract_graphics_section(self, section: BeautifulSoup, specs: Dict[str, str]):
        """Extract detailed graphics information."""
        graphics_selectors = [
            'td:-soup-contains("Graphics")',
            'td:-soup-contains("GPU")',
            'td:-soup-contains("Graphics Card")'
        ]
        
        for selector in graphics_selectors:
            elem = section.select_one(selector)
            if elem:
                graphics_info = self._clean_text(elem.text)
                specs['graphics'] = graphics_info
                specs['graphics_card'] = graphics_info
                break

    def _extract_processor_info(self, specs: Dict[str, str]) -> Dict[str, str]:
        """Extract processor details."""
        result = {
            "brand": "",
            "model": "",
            "generation": "",
            "speed": "",
            "cores": ""
        }

        # Try multiple spec keys for processor info
        processor_keys = ['processor_type', 'processor', 'cpu_model']
        processor_info = next((specs.get(key, '') for key in processor_keys if key in specs), '')
        
        if processor_info:
            # Extract brand
            brands = ["Intel", "AMD", "Apple"]
            for brand in brands:
                if brand.lower() in processor_info.lower():
                    result["brand"] = brand
                    break

            # Extract generation
            gen_match = re.search(r'(\d+)(?:th|st|nd|rd)\s*Gen', processor_info, re.IGNORECASE)
            if gen_match:
                result["generation"] = f"{gen_match.group(1)}th Gen"

            # Extract model
            cpu_models = {
                r'i3': "Core i3",
                r'i5': "Core i5",
                r'i7': "Core i7",
                r'i9': "Core i9",
                r'ryzen\s*\d': "Ryzen",
                r'celeron': "Celeron",
                r'pentium': "Pentium"
            }
            
            for pattern, model in cpu_models.items():
                if re.search(pattern, processor_info, re.IGNORECASE):
                    result["model"] = model
                    break

            # Extract speed
            speed_match = re.search(r'([\d.]+)\s*(?:GHz|MHz)', processor_info, re.IGNORECASE)
            if speed_match:
                speed = float(speed_match.group(1))
                unit = "MHz" if "MHz" in speed_match.group().upper() else "GHz"
                result["speed"] = f"{speed} {unit}"

            # Extract cores
            cores_match = re.search(r'(\d+)\s*(?:cores?|processors?)', processor_info, re.IGNORECASE)
            if cores_match:
                result["cores"] = cores_match.group(1)

        return result

    def _extract_ram_info(self, specs: Dict[str, str]) -> Dict[str, str]:
        """Extract RAM specifications."""
        result = {
            "size": "",
            "type": "",
            "speed": ""
        }

        # Try multiple keys for RAM info
        ram_keys = ['ram', 'memory', 'ram_memory_installed_size']
        ram_info = next((specs.get(key, '') for key in ram_keys if key in specs), '')
        
        if ram_info:
            # Extract RAM size
            size_match = re.search(r'(\d+)\s*GB', ram_info, re.IGNORECASE)
            if size_match:
                result["size"] = f"{size_match.group(1)}GB"
            
            # Extract RAM type
            ram_types = ["DDR4", "DDR5", "LPDDR4", "LPDDR4X", "LPDDR5"]
            for ram_type in ram_types:
                if ram_type in ram_info:
                    result["type"] = ram_type
                    break
            
            # Extract RAM speed
            speed_match = re.search(r'(\d+)\s*MHz', ram_info, re.IGNORECASE)
            if speed_match:
                result["speed"] = f"{speed_match.group(1)}MHz"

        return result

    def _extract_storage_info(self, specs: Dict[str, str]) -> Dict[str, str]:
        """Extract storage specifications."""
        result = {
            "primary_type": "",
            "primary_capacity": "",
            "secondary_type": "",
            "secondary_capacity": ""
        }

        # Try multiple keys for storage info
        storage_keys = ['hard_drive', 'storage', 'hard_disk']
        storage_info = next((specs.get(key, '') for key in storage_keys if key in specs), '')

        if storage_info:
            storage_types = {
                "SSD": r'(\d+)\s*(?:GB|TB)?\s*SSD',
                "HDD": r'(\d+)\s*(?:GB|TB)?\s*HDD',
                "eMMC": r'(\d+)\s*(?:GB|TB)?\s*eMMC',
                "NVMe": r'(\d+)\s*(?:GB|TB)?\s*NVMe'
            }
            
            found_primary = False
            for storage_type, pattern in storage_types.items():
                matches = list(re.finditer(pattern, storage_info, re.IGNORECASE))
                for idx, match in enumerate(matches):
                    size = match.group(1)
                    unit = "TB" if "TB" in storage_info[match.start():match.end()] else "GB"
                    
                    if not found_primary:
                        result["primary_type"] = storage_type
                        result["primary_capacity"] = f"{size}{unit}"
                        found_primary = True
                    else:
                        result["secondary_type"] = storage_type
                        result["secondary_capacity"] = f"{size}{unit}"
                        break

        return result

    def _extract_display_info(self, specs: Dict[str, str]) -> Dict[str, str]:
        """Extract display specifications."""
        result = {
            "size": "",
            "resolution": "",
            "type": "",
            "refresh_rate": "",
            "nits": ""
        }

        # Try multiple keys for display info
        display_keys = ['display', 'screen', 'display_resolution']
        display_info = ' '.join(specs.get(key, '') for key in display_keys if key in specs)

        if display_info:
            # Extract display size
            size_match = re.search(r'(\d+\.?\d*)\s*inches?', display_info, re.IGNORECASE)
            if size_match:
                result["size"] = f"{size_match.group(1)} inches"
            
            # Extract resolution
            resolution_patterns = [
                r'(\d+\s*[xX×]\s*\d+)',
                r'(HD|Full HD|FHD|QHD|2K|4K|UHD)',
                r'(\d+p)'
            ]
            for pattern in resolution_patterns:
                match = re.search(pattern, display_info)
                if match:
                    result["resolution"] = match.group(1)
                    break
            
            # Extract display type
            display_types = ["IPS", "OLED", "LED", "LCD", "Mini LED", "VA", "TN"]
            for d_type in display_types:
                if d_type in display_info:
                    result["type"] = d_type
                    break
            
            # Extract refresh rate
            refresh_match = re.search(r'(\d+)\s*Hz', display_info)
            if refresh_match:
                result["refresh_rate"] = f"{refresh_match.group(1)}Hz"
            
            # Extract brightness
            nits_match = re.search(r'(\d+)\s*nits?', display_info, re.IGNORECASE)
            if nits_match:
                result["nits"] = f"{nits_match.group(1)} nits"

        return result

    def _extract_graphics_info(self, specs: Dict[str, str]) -> Dict[str, str]:
        """Extract graphics specifications."""
        result = {
            "type": "",
            "brand": "",
            "model": "",
            "memory": ""
        }

        # Try multiple keys for graphics info
        graphics_keys = ['graphics_card', 'graphics_coprocessor', 'gpu', 'video_card']
        graphics_info = ' '.join(specs.get(key, '') for key in graphics_keys if key in specs)
        
        if graphics_info:
            # Determine if integrated or dedicated
            integrated_patterns = ['integrated', 'intel uhd', 'intel iris', 'amd radeon graphics']
            dedicated_patterns = ['nvidia', 'rtx', 'gtx', 'radeon rx']
            
            if any(pattern in graphics_info.lower() for pattern in integrated_patterns):
                result["type"] = "Integrated"
            elif any(pattern in graphics_info.lower() for pattern in dedicated_patterns):
                result["type"] = "Dedicated"
            
            # Extract brand
            brands = {
                "NVIDIA": r'(?:NVIDIA|GeForce|RTX|GTX)',
                "AMD": r'(?:AMD|Radeon(?!\s+Graphics))',
                "Intel": r'(?:Intel|UHD|Iris)'
            }
            for brand, pattern in brands.items():
                if re.search(pattern, graphics_info, re.IGNORECASE):
                    result["brand"] = brand
                    break
            
            # Extract model
            model_patterns = [
                (r'(RTX\s*\d+(?:\s*[A-Za-z]*)?)', 'NVIDIA'),
                (r'(GTX\s*\d+(?:\s*[A-Za-z]*)?)', 'NVIDIA'),
                (r'(Radeon\s*RX\s*\d+(?:\s*[A-Za-z]*)?)', 'AMD'),
                (r'(Iris\s*Xe(?:\s*[A-Za-z]*)?)', 'Intel'),
                (r'(UHD\s*\d+(?:\s*[A-Za-z]*)?)', 'Intel')
            ]
            
            for pattern, brand in model_patterns:
                if result["brand"] == brand:
                    match = re.search(pattern, graphics_info, re.IGNORECASE)
                    if match:
                        result["model"] = match.group(1)
                        break
            
            # Extract memory
            memory_patterns = [
                r'(\d+)\s*GB\s*(?:GDDR|VRAM)',
                r'(\d+)\s*GB'
            ]
            for pattern in memory_patterns:
                match = re.search(pattern, graphics_info, re.IGNORECASE)
                if match:
                    result["memory"] = f"{match.group(1)}GB"
                    break

        return result

    def _extract_battery_info(self, specs: Dict[str, str]) -> Dict[str, str]:
        """Extract battery specifications."""
        result = {
            "capacity": "",
            "type": "",
            "watt_hours": "",
            "cells": ""
        }

        # Try multiple keys for battery info
        battery_keys = ['battery', 'battery_description', 'battery_life']
        battery_info = ' '.join(specs.get(key, '') for key in battery_keys if key in specs)
        
        if battery_info:
            # Extract capacity in mAh
            capacity_match = re.search(r'(\d+)\s*mAh', battery_info, re.IGNORECASE)
            if capacity_match:
                result["capacity"] = f"{capacity_match.group(1)}mAh"
            
            # Extract battery type
            battery_types = [
                ("Li-ion", r'lithium[- ]ion'),
                ("Lithium Polymer", r'lithium[- ]polymer'),
                ("LiPo", r'lipo\b')
            ]
            for b_type, pattern in battery_types:
                if re.search(pattern, battery_info, re.IGNORECASE):
                    result["type"] = b_type
                    break
            
            # Extract watt hours
            wh_match = re.search(r'(\d+\.?\d*)\s*Wh', battery_info)
            if wh_match:
                result["watt_hours"] = f"{wh_match.group(1)}Wh"
            
            # Extract cell count
            cells_match = re.search(r'(\d+)[-\s]cell', battery_info, re.IGNORECASE)
            if cells_match:
                result["cells"] = f"{cells_match.group(1)}-cell"

        return result

    def _extract_ports_info(self, specs: Dict[str, str]) -> List[str]:
        """Extract ports and connectivity information."""
        ports = set()  # Use set to automatically handle duplicates

        # Try multiple keys for ports info
        port_keys = ['ports', 'connectivity_type', 'hardware_interface', 'interfaces']
        ports_info = ' '.join(specs.get(key, '') for key in port_keys if key in specs)
        
        if ports_info:
            port_patterns = [
                # USB ports
                r'USB (?:\d\.?\d?)(?: Type-[A-C])?',
                r'Type-C',
                r'Thunderbolt\s*\d?',
                
                # Video ports
                r'HDMI ?\d?\.?\d?[a-z]?',
                r'DisplayPort(?:\s*\d?\.?\d?)?',
                r'VGA',
                r'D-Sub',
                
                # Network ports
                r'RJ45',
                r'Ethernet',
                
                # Audio ports
                r'(?:3\.5mm|audio|headphone|mic)(?:\s+)?(?:combo)?(?:\s+)?jack',
                r'Audio(?:\s+)?(?:Combo)?(?:\s+)?Jack',
                
                # Card readers
                r'SD card reader',
                r'microSD slot',
                
                # Other
                r'Kensington lock'
            ]
            
            for pattern in port_patterns:
                matches = re.finditer(pattern, ports_info, re.IGNORECASE)
                for match in matches:
                    ports.add(match.group().strip())

        return sorted(list(ports))  # Convert back to sorted list

    def _extract_dimensions_info(self, specs: Dict[str, str]) -> Dict[str, float]:
        """Extract physical dimensions and weight."""
        result = {
            "length": 0.0,
            "width": 0.0,
            "height": 0.0,
            "weight": 0.0
        }

        # Try multiple keys for dimensions
        dimension_keys = ['dimensions', 'product_dimensions', 'item_dimensions']
        dimensions_info = next((specs.get(key, '') for key in dimension_keys if key in specs), '')
        
        if dimensions_info:
            # Try different dimension patterns
            dimension_patterns = [
                r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*(?:cm|mm|inches)',
                r'(\d+\.?\d*)\s*[×x]\s*(\d+\.?\d*)\s*[×x]\s*(\d+\.?\d*)\s*(?:cm|mm|inches)'
            ]
            
            for pattern in dimension_patterns:
                match = re.search(pattern, dimensions_info, re.IGNORECASE)
                if match:
                    # Convert to cm if in mm or inches
                    multiplier = 0.1 if 'mm' in dimensions_info.lower() else (2.54 if 'inches' in dimensions_info.lower() else 1.0)
                    result["length"] = round(float(match.group(1)) * multiplier, 2)
                    result["width"] = round(float(match.group(2)) * multiplier, 2)
                    result["height"] = round(float(match.group(3)) * multiplier, 2)
                    break

        # Extract weight
        weight_keys = ['weight', 'item_weight', 'product_weight']
        weight_info = next((specs.get(key, '') for key in weight_keys if key in specs), '')
        
        if weight_info:
            weight_match = re.search(r'(\d+\.?\d*)\s*(kg|pounds?|lbs?|g)', weight_info, re.IGNORECASE)
            if weight_match:
                weight = float(weight_match.group(1))
                unit = weight_match.group(2).lower()
                
                # Convert to kg
                if unit.startswith('pound') or unit.startswith('lb'):
                    weight *= 0.453592
                elif unit.startswith('g'):
                    weight *= 0.001
                
                result["weight"] = round(weight, 2)

        return result

    def _extract_brand(self, title: str, specs: Dict[str, str]) -> str:
        """Extract brand information from title or specifications."""
        common_brands = [
            "HP", "Dell", "Lenovo", "ASUS", "Acer", "MSI", "Apple", 
            "Microsoft", "Razer", "Samsung", "LG", "Toshiba", "Fujitsu",
            "Alienware", "ROG", "Predator", "VAIO", "Huawei", "Honor",
            "Xiaomi", "Realme", "RedmiBook"
        ]
        
        # First check if brand is explicitly mentioned in specs
        brand_keys = ['brand', 'brand_name', 'manufacturer']
        for key in brand_keys:
            if key in specs:
                brand_value = specs[key].strip()
                # Check if the brand value matches any known brand (case-insensitive)
                for brand in common_brands:
                    if brand.lower() in brand_value.lower():
                        return brand
        
        # Then look for brand in title
        title_lower = title.lower()
        for brand in common_brands:
            if brand.lower() in title_lower:
                return brand
        
        return "Unknown"