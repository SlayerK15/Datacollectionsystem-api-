# spiders/flipkart_spider.py
from .base_spider import BaseSpider
from database.models import Laptop, LaptopSpecs
from core.rate_limiter import RateLimiter
from core.proxy_manager import ProxyManager
from core.data_cleaner import DataCleaner
from datetime import datetime
from bs4 import BeautifulSoup
import logging

class FlipkartSpider(BaseSpider):
    def __init__(self, session, rate_limiter: RateLimiter, proxy_manager: ProxyManager):
        super().__init__(session)
        self.rate_limiter = rate_limiter
        self.proxy_manager = proxy_manager
        self.base_url = "https://www.flipkart.com/laptops"
        self.logger = logging.getLogger(__name__)
        self.data_cleaner = DataCleaner()

    async def extract_product_links(self, url: str) -> List[str]:
        await self.rate_limiter.acquire('flipkart.com')
        proxy = await self.proxy_manager.get_proxy()
        
        try:
            content = await self.get_page_content(url, proxy)
            soup = BeautifulSoup(content, 'html.parser')
            links = []
            
            for item in soup.select('div._1AtVbE'):
                product_url = item.select_one('a._1fQZEK')
                if product_url:
                    links.append(f"https://www.flipkart.com{product_url['href']}")
            
            return links[:10]  # Limit for testing
        except Exception as e:
            self.logger.error(f"Error extracting product links: {str(e)}")
            return []

    async def extract_product_data(self, url: str) -> Optional[Laptop]:
        await self.rate_limiter.acquire('flipkart.com')
        proxy = await self.proxy_manager.get_proxy()
        
        try:
            content = await self.get_page_content(url, proxy)
            soup = BeautifulSoup(content, 'html.parser')

            # Extract basic information
            title = soup.select_one('span.B_NuCI').text.strip()
            current_price = self.data_cleaner.clean_price(
                soup.select_one('div._30jeq3._16Jk6d').text)
            original_price = self.data_cleaner.clean_price(
                soup.select_one('div._3I9_wc._2p6lqe').text)

            # Extract specifications
            specs = {}
            spec_table = soup.select('div._14cfVK')
            for row in spec_table:
                label = row.select_one('td:nth-child(1)').text.strip()
                value = row.select_one('td:nth-child(2)').text.strip()
                specs[label] = value

            # Create LaptopSpecs object
            laptop_specs = LaptopSpecs(
                processor=self.data_cleaner.clean_processor_info(
                    specs.get("Processor Type", "")),
                ram=self.data_cleaner.clean_ram_info(
                    specs.get("RAM", "")),
                storage=self.data_cleaner.clean_storage_info(
                    specs.get("Storage", "")),
                display={
                    "size": specs.get("Display Size", ""),
                    "resolution": specs.get("Resolution", ""),
                    "type": specs.get("Display Type", "")
                },
                graphics={
                    "type": specs.get("Graphics Card", ""),
                    "memory": specs.get("Graphics Memory", "")
                },
                os=specs.get("Operating System", ""),
                battery={
                    "capacity": specs.get("Battery Capacity", ""),
                    "type": specs.get("Battery Type", "")
                },
                ports=specs.get("Ports", "").split(","),
                dimensions={
                    "weight": float(re.sub(r'[^\d.]', '', 
                        specs.get("Weight", "0"))),
                    "thickness": specs.get("Thickness", "")
                }
            )

            return Laptop(
                product_id=url.split('pid=')[-1].split('&')[0],
                source="Flipkart",
                url=url,
                title=title,
                brand=specs.get("Brand", ""),
                model=specs.get("Model Number", ""),
                current_price=current_price,
                original_price=original_price,
                specifications=laptop_specs,
                last_updated=datetime.utcnow()
            )

        except Exception as e:
            self.logger.error(f"Error extracting product data: {str(e)}")
            return None