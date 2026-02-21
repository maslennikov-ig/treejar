from __future__ import annotations

from src.core.database import get_db
from src.core.redis import get_redis

# Re-export for convenient imports
__all__ = ["get_db", "get_redis"]
