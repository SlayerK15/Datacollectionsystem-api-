# core/proxy_manager.py
import aiohttp
import asyncio
import random
from typing import List, Optional
from datetime import datetime, timedelta
from config.settings import PROXY_REFRESH_INTERVAL, PROXY_PROVIDERS

class ProxyManager:
    def __init__(self):
        self.proxies: List[str] = []
        self.last_refresh: Optional[datetime] = None

    async def get_proxy(self) -> Optional[str]:
        if not self.proxies or self._should_refresh():
            await self.refresh_proxies()
        return random.choice(self.proxies) if self.proxies else None

    async def refresh_proxies(self):
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [self._fetch_proxies(session, url) for url in PROXY_PROVIDERS]
                proxy_lists = await asyncio.gather(*tasks)
                self.proxies = [proxy for sublist in proxy_lists for proxy in sublist]
                self.last_refresh = datetime.now()
        except Exception as e:
            print(f"Error refreshing proxies: {str(e)}")

    async def _fetch_proxies(self, session: aiohttp.ClientSession, url: str) -> List[str]:
        try:
            async with session.get(url) as response:
                data = await response.json()
                return self._parse_proxy_response(data)
        except Exception:
            return []

    def _parse_proxy_response(self, data: dict) -> List[str]:
        # Implement parsing logic based on your proxy provider's response format
        return []

    def _should_refresh(self) -> bool:
        if not self.last_refresh:
            return True
        return (datetime.now() - self.last_refresh).seconds >= PROXY_REFRESH_INTERVAL
