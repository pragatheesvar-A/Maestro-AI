"""
Event bus abstraction: Redis Streams when available, transparent in-process
asyncio fallback otherwise. Designed so a future Kafka/Redpanda backend can
be dropped in behind the same publish()/consume() interface (per spec:
"Design architecture so Kafka/Redpanda can replace it later").
"""
import asyncio
import json
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger("smartalloc.events")
settings = get_settings()

STREAM_KEY = "smartalloc:allocation_events"

_redis_client = None
_redis_checked = False
_memory_queue: "asyncio.Queue" = asyncio.Queue()


def _get_redis():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    try:
        import redis
        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=0.5)
        client.ping()
        _redis_client = client
        logger.info("Event bus: connected to Redis Streams at %s", settings.REDIS_URL)
    except Exception as e:
        logger.warning("Event bus: Redis unavailable (%s). Using in-process fallback.", e)
        _redis_client = None
    return _redis_client


async def publish_event(event_type: str, payload: dict):
    data = {"event_type": event_type, "payload": payload}
    client = _get_redis()
    if client is not None:
        try:
            client.xadd(STREAM_KEY, {"data": json.dumps(data)})
            return
        except Exception as e:
            logger.warning("Redis publish failed (%s), falling back to memory queue", e)
    await _memory_queue.put(data)


def event_bus_backend() -> str:
    return "redis-streams" if _get_redis() is not None else "in-process-fallback"
