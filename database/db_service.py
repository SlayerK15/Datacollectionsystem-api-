# database/db_service.py
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List, Dict
import logging
from datetime import datetime
from config.settings import MONGODB_URI, DATABASE_NAME, COLLECTION_NAME
from .models import Laptop

class DatabaseService:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DATABASE_NAME]
        self.collection = self.db[COLLECTION_NAME]
        self.logger = logging.getLogger(__name__)

    async def insert_laptop(self, laptop: Laptop) -> bool:
        try:
            # Update existing or insert new
            result = await self.collection.update_one(
                {"product_id": laptop.product_id},
                {
                    "$set": laptop.dict(exclude={"first_seen"}),
                    "$setOnInsert": {"first_seen": datetime.utcnow()}
                },
                upsert=True
            )
            return bool(result.acknowledged)
        except Exception as e:
            self.logger.error(f"Error inserting laptop: {str(e)}")
            return False

    async def get_laptop(self, product_id: str) -> Optional[Laptop]:
        try:
            doc = await self.collection.find_one({"product_id": product_id})
            return Laptop(**doc) if doc else None
        except Exception as e:
            self.logger.error(f"Error retrieving laptop: {str(e)}")
            return None

    async def mark_unavailable(self, product_id: str) -> bool:
        try:
            result = await self.collection.update_one(
                {"product_id": product_id},
                {
                    "$set": {
                        "in_stock": False,
                        "last_updated": datetime.utcnow()
                    }
                }
            )
            return bool(result.modified_count)
        except Exception as e:
            self.logger.error(f"Error marking laptop unavailable: {str(e)}")
            return False

    async def get_price_history(self, product_id: str) -> List[Dict]:
        try:
            pipeline = [
                {"$match": {"product_id": product_id}},
                {"$project": {
                    "price_history": {
                        "$map": {
                            "input": "$price_updates",
                            "as": "pu",
                            "in": {
                                "price": "$$pu.price",
                                "date": "$$pu.date"
                            }
                        }
                    }
                }}
            ]
            result = await self.collection.aggregate(pipeline).to_list(None)
            return result[0]["price_history"] if result else []
        except Exception as e:
            self.logger.error(f"Error retrieving price history: {str(e)}")
            return []

    async def cleanup_old_records(self, days: int = 90) -> int:
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = await self.collection.delete_many({
                "last_updated": {"$lt": cutoff_date},
                "in_stock": False
            })
            return result.deleted_count
        except Exception as e:
            self.logger.error(f"Error cleaning up old records: {str(e)}")
            return 0