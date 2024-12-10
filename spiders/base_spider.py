# spiders/base_spider.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import aiohttp
import asyncio
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from database.models import Laptop
from core.rate_limiter import RateLimiter
from core.proxy_manager import ProxyManager

class BaseSpider(ABC):
    def __init__(self, 
                 session: aiohttp.ClientSession,
                 rate_limiter: RateLimiter,
                 proxy_manager: ProxyManager):
        self.session = session
        self.rate_limiter = rate_limiter
        self.proxy_manager = proxy_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }

    async def get_page_content(self, url: str, proxy: Optional[str] = None) -> str:
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Rate limiting
                await self.rate_limiter.acquire(self._get_domain(url))
                
                # Get proxy if none provided
                if not proxy:
                    proxy = await self.proxy_manager.get_proxy()
                
                async with self.session.get(
                    url,
                    headers=self.headers,
                    proxy=proxy,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 404:
                        raise ValueError(f"Page not found: {url}")
                    elif response.status in [403, 429]:
                        self.logger.warning(f"Rate limited on {url}")
                        await asyncio.sleep(5 * (retry_count + 1))
                    else:
                        raise ValueError(f"Unexpected status code: {response.status}")
                        
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout on {url}")
            except Exception as e:
                self.logger.error(f"Error fetching {url}: {str(e)}")
            
            retry_count += 1
            await asyncio.sleep(retry_count * 2)
        
        raise Exception(f"Failed to fetch {url} after {max_retries} retries")

    @abstractmethod
    async def extract_product_links(self, url: str) -> List[str]:
        """Extract product links from the listing page."""
        pass

    @abstractmethod
    async def extract_product_data(self, url: str) -> Optional[Laptop]:
        """Extract detailed product data from the product page."""
        pass

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for rate limiting."""
        return url.split('/')[2]

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        return ' '.join(text.strip().split())

    def _extract_price(self, price_text: str) -> float:
        """Extract and convert price to float."""
        try:
            price = ''.join(filter(str.isdigit, price_text.replace(',', '')))
            return float(price)
        except (ValueError, AttributeError):
            return 0.0

    async def _process_pagination(self, base_url: str, max_pages: int = 5) -> List[str]:
        """Handle pagination for product listings."""
        all_links = []
        for page in range(1, max_pages + 1):
            try:
                page_url = f"{base_url}&page={page}"
                links = await self.extract_product_links(page_url)
                if not links:
                    break
                all_links.extend(links)
            except Exception as e:
                self.logger.error(f"Error processing page {page}: {str(e)}")
                break
        return list(set(all_links))  # Remove duplicates
