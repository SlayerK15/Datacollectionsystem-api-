# core/rate_limiter.py
import asyncio
import time
from config.settings import RATE_LIMIT

class RateLimiter:
    def __init__(self, rate_limit: float = RATE_LIMIT):
        self.rate_limit = rate_limit
        self.last_request_time = {}

    async def acquire(self, domain: str):
        current_time = time.time()
        if domain in self.last_request_time:
            time_passed = current_time - self.last_request_time[domain]
            if time_passed < (1 / self.rate_limit):
                await asyncio.sleep((1 / self.rate_limit) - time_passed)
        
        self.last_request_time[domain] = time.time()
