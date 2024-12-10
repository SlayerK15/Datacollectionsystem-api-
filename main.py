# main.py
import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from core.scheduler import Scheduler
from core.spider_manager import SpiderManager
from core.proxy_manager import ProxyManager
from core.rate_limiter import RateLimiter
from database.db_service import DatabaseService

class DataCollectionSystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db_service = DatabaseService()
        self.proxy_manager = ProxyManager()
        self.rate_limiter = RateLimiter()
        self.spider_manager = SpiderManager(
            self.db_service
        )
        self.scheduler = Scheduler(self.spider_manager)
        self._shutdown_event: Optional[asyncio.Event] = None
        self.running = True

    async def start(self):
        self._shutdown_event = asyncio.Event()
        
        try:
            self.logger.info(f"Starting Data Collection System at {datetime.utcnow()}")
            
            # Handle shutdown gracefully
            if sys.platform == 'win32':
                # Windows specific handling
                import win32api
                def handler(sig, func=None):
                    self.running = False
                    asyncio.create_task(self.shutdown())
                win32api.SetConsoleCtrlHandler(handler, True)
            else:
                # Unix-like systems
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop = asyncio.get_running_loop()
                    loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

            # Start the scheduler
            scheduler_task = asyncio.create_task(self.scheduler.start())
            await self._shutdown_event.wait()
            await scheduler_task
            
        except Exception as e:
            self.logger.error(f"Error in main system: {str(e)}")
        finally:
            await self.cleanup()

    async def shutdown(self):
        self.logger.info("Initiating shutdown...")
        if self._shutdown_event:
            self._shutdown_event.set()

    async def cleanup(self):
        self.logger.info("Cleaning up resources...")
        await self.scheduler.stop()
        # Close database connections
        self.db_service.client.close()
        self.logger.info("Cleanup completed")

class HealthCheck:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.logger = logging.getLogger(__name__)

    async def check_system_health(self) -> Dict[str, Any]:
        try:
            # Check database connection
            db_status = await self._check_database()
            
            # Check recent scraping activity
            scraping_status = await self._check_scraping_activity()
            
            # Check proxy availability
            proxy_status = await self._check_proxies()

            return {
                "status": "healthy" if all([
                    db_status["healthy"],
                    scraping_status["healthy"],
                    proxy_status["healthy"]
                ]) else "unhealthy",
                "components": {
                    "database": db_status,
                    "scraping": scraping_status,
                    "proxies": proxy_status
                },
                "timestamp": datetime.utcnow()
            }
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def _check_database(self) -> Dict[str, Any]:
        try:
            # Ping database
            await self.db_service.collection.find_one({})
            return {"healthy": True}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _check_scraping_activity(self) -> Dict[str, Any]:
        try:
            # Check for recent updates
            cutoff = datetime.utcnow() - timedelta(hours=24)
            count = await self.db_service.collection.count_documents({
                "last_updated": {"$gt": cutoff}
            })
            return {
                "healthy": count > 0,
                "updates_24h": count
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _check_proxies(self) -> Dict[str, Any]:
        try:
            proxy_count = len(await self.proxy_manager.get_available_proxies())
            return {
                "healthy": proxy_count > 0,
                "available_proxies": proxy_count
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logging.error(f"Caught exception: {msg}")

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('data_collection.log'),
            logging.StreamHandler()
        ]
    )

    # Start the system
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(handle_exception)
    
    try:
        system = DataCollectionSystem()
        loop.run_until_complete(system.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()