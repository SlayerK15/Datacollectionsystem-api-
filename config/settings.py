# config/settings.py
MONGODB_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "laptop_data"
COLLECTION_NAME = "laptops"

# Scraping configurations
AMAZON_BASE_URL = "https://www.amazon.in/s?k=laptops"
FLIPKART_BASE_URL = "https://www.flipkart.com/laptops"

SCRAPING_INTERVAL = 3600  # 1 hour
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
RATE_LIMIT = 1  # requests per second

# Proxy settings
USE_PROXIES = True
PROXY_REFRESH_INTERVAL = 600  # 10 minutes
PROXY_PROVIDERS = [
    "https://proxy-provider1.com/api",
    "https://proxy-provider2.com/api"
]