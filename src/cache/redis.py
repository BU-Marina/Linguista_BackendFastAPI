"""..."""

import os
import aioredis

from dotenv import load_dotenv

load_dotenv()

redis = aioredis.from_url(os.getenv("REDIS_URL"), encoding="utf-8", decode_responses=True)
