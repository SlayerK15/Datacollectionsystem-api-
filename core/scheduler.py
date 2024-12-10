# core/scheduler.py
import asyncio
import logging
from datetime import datetime
from typing import Optional
from config.settings import SCRAPING_INTERVAL

class Scheduler:
    def __init__(self, spider_manager):
        self.spider_manager = spider_manager
        self.running = False
        self.logger = logging.getLogger(__name__)
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self.running = True
        self._task = asyncio.create_task(self._run())
        await self._task

    async def _run(self):
        while self.running:
            try:
                self.logger.info(f"Starting scheduled scan at {datetime.utcnow()}")
                await self.spider_manager.run_spiders()
                await asyncio.sleep(SCRAPING_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error in scheduler: {str(e)}")
                await asyncio.sleep(60)

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass