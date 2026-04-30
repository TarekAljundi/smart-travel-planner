# backend/app/services/webhook.py
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import get_settings
from app.models.schemas import TripPlan
import structlog

settings = get_settings()
log = structlog.get_logger()


@retry(
    stop=stop_after_attempt(settings.webhook_retry_attempts),
    wait=wait_exponential(
        multiplier=settings.webhook_retry_backoff_multiplier,
        min=settings.webhook_retry_backoff_min,
        max=settings.webhook_retry_backoff_max,
    ),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=False,
)
async def deliver_webhook(payload: TripPlan) -> bool:
    async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
        resp = await client.post(settings.webhook_url, json=payload.model_dump())
        resp.raise_for_status()
    log.info("webhook.delivered")
    return True


async def send_webhook(payload: TripPlan):
    try:
        await deliver_webhook(payload)
    except Exception as e:
        log.error("webhook.failed", error=str(e))