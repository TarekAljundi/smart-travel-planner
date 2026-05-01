# backend/app/routes/trips.py
import json
import structlog
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session
from app.dependencies import verify_token_manually
from app.services.agent import run_agent_and_stream_synthesis
from app.services.webhook import send_webhook_sync
from app.models.db import AgentRun, User
from app.models.schemas import TripPlan
from app.config import get_settings

router = APIRouter(prefix="/api", tags=["trips"])
log = structlog.get_logger()
settings = get_settings()

_executor = ThreadPoolExecutor(max_workers=2)


def _persist_and_email_sync(
    user_id: int,
    query: str,
    final_text: str,
    user_email: str,
    sync_db_url: str,
):
    """
    Runs in a separate thread – completely independent of the async event loop.
    Skips the email if the agent has no knowledge about the requested destination.
    """
    try:
        engine = create_engine(sync_db_url)
        with Session(engine) as session:
            run = AgentRun(user_id=user_id, query=query, final_answer=final_text)
            session.add(run)
            session.commit()
            log.info("agent.run.persisted", run_id=run.id)

        # ---- Only send email if the response does NOT indicate missing knowledge ----
        if user_email and final_text and "I don't have enough information" not in final_text:
            plan = TripPlan(
                user_id=user_id,
                query=query,
                plan=final_text,
                user_email=user_email,
            )
            send_webhook_sync(plan)
            log.info("email.sent", to=user_email)
        else:
            log.info("email.skipped", reason="no knowledge or no user email")
    except Exception as e:
        log.error("persist_or_webhook_failed", error=str(e))


@router.get("/plan-trip")
async def plan_trip(
    query: str,
    token: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    # ---------- 1. Verify JWT ----------
    user_id = await verify_token_manually(token, request.app.state.engine)
    if not user_id:
        return StreamingResponse(
            content=iter(['data: {"error": "Invalid token"}\n\n']),
            media_type="text/event-stream",
        )

    # ---------- 2. Load dependencies ----------
    classifier = request.app.state.classifier
    embedder = request.app.state.embedder
    session_factory = request.app.state.async_session_factory

    if classifier is None:
        return StreamingResponse(
            content=iter(['data: {"error": "ML model not loaded"}\n\n']),
            media_type="text/event-stream",
        )

    # ---------- 3. Fetch user email ----------
    async with session_factory() as session:
        stmt = select(User.email).where(User.id == user_id)
        result = await session.execute(stmt)
        user_email = result.scalar_one_or_none()

    if not user_email:
        log.warning("user.email_not_found", user_id=user_id)
    else:
        log.info("user.email_found", email=user_email)

    sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg2")

    # ---------- 4. SSE generator ----------
    email_sent = False
    async def event_generator():
        nonlocal email_sent
        final_text = ""
        try:
            async for sse_data in run_agent_and_stream_synthesis(
                query=query,
                classifier=classifier,
                embedder=embedder,
                session_factory=session_factory,
            ):
                yield sse_data
                if '"type": "token"' in sse_data:
                    try:
                        payload = json.loads(sse_data.replace("data: ", ""))
                        final_text += payload.get("content", "")
                    except Exception:
                        pass
        except asyncio.CancelledError:
            log.warning("client.disconnected_during_stream")
        finally:
            if not email_sent and user_email and final_text:
             email_sent = True
            _executor.submit(
                _persist_and_email_sync,
                user_id,
                query,
                final_text,
                user_email,
                sync_db_url,
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")