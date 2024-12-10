# core/spider_manager.py
import asyncio
import logging
from typing import List
import aiohttp
from spiders.amazon_spider import AmazonSpider
from database.db_service import DatabaseService
from core.rate_limiter import RateLimiter
from core.proxy_manager import ProxyManager

class SpiderManager:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.logger = logging.getLogger(__name__)
        self.rate_limiter = RateLimiter()
        self.proxy_manager = ProxyManager()

    async def run_spiders(self):
        async with aiohttp.ClientSession() as session:
            spider = AmazonSpider(session, self.rate_limiter, self.proxy_manager)
            try:
                # Get initial product links
                self.logger.info("Starting product link extraction")
                initial_links = await spider.extract_product_links(spider.base_url)
                self.logger.info(f"Initial product links found: {len(initial_links)}")

                # Process pagination if needed
                product_links = await spider._process_pagination(spider.base_url)
                self.logger.info(f"Total product links after pagination: {len(product_links)}")

                # Process each product
                for index, link in enumerate(product_links, 1):
                    try:
                        self.logger.info(f"Processing product {index}/{len(product_links)}")
                        self.logger.info(f"Fetching data from: {link}")
                        
                        # Add delay between requests
                        await asyncio.sleep(3)  # 3 seconds delay
                        
                        # Extract product data
                        product = await spider.extract_product_data(link)
                        
                        if product:
                            self.logger.info(f"Saving product data for: {link}")
                            await self.db_service.insert_laptop(product)
                            self.logger.info(f"Successfully processed: {link}")
                        else:
                            self.logger.warning(f"No data extracted for: {link}")

                    except Exception as e:
                        self.logger.error(f"Error processing {link}: {str(e)}", exc_info=True)
                        continue  # Continue with next product even if current one fails
                        
                self.logger.info("Completed processing all products")

            except Exception as e:
                self.logger.error(f"Spider execution error: {str(e)}", exc_info=True)
                raise  # Re-raise the exception to be handled by the main error handler

    async def stop(self):
        """Cleanup method to be called when shutting down"""
        self.logger.info("Stopping spider manager")
        # Add any cleanup code here if needed