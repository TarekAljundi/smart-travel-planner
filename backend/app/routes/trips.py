# backend/app/routes/trips.py
import json
import structlog
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.dependencies import verify_token_manually
from app.services.agent import run_agent_and_stream_synthesis
from app.services.webhook import send_webhook
from app.models.db import AgentRun
from app.models.schemas import TripPlan

router = APIRouter(prefix="/api", tags=["trips"])
log = structlog.get_logger()


@router.get("/plan-trip")
async def plan_trip(
    query: str,
    token: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    # Manual JWT verification (EventSource can't send headers)
    user_id = await verify_token_manually(token, request.app.state.engine)
    if not user_id:
        return StreamingResponse(
            content=iter(['data: {"error": "Invalid token"}\n\n']),
            media_type="text/event-stream",
        )

    classifier = request.app.state.classifier
    embedder = request.app.state.embedder
    session_factory = request.app.state.async_session_factory

    if classifier is None:
        return StreamingResponse(
            content=iter(['data: {"error": "ML model not loaded"}\n\n']),
            media_type="text/event-stream",
        )

    async def event_generator():
        final_text = ""
        async for sse_data in run_agent_and_stream_synthesis(
            query=query,
            classifier=classifier,
            embedder=embedder,
            session_factory=session_factory,
        ):
            yield sse_data
            # Accumulate the final answer from token events
            if '"type": "token"' in sse_data:
                try:
                    payload = json.loads(sse_data.replace("data: ", ""))
                    final_text += payload["content"]
                except Exception:
                    pass

        # Persist run and schedule webhook after streaming finishes
        try:
            async with session_factory() as session:
                run = AgentRun(user_id=user_id, query=query, final_answer=final_text)
                session.add(run)
                await session.commit()
                log.info("agent.run.persisted", run_id=run.id)

            plan = TripPlan(
                user_id=user_id,
                query=query,
                plan=final_text,
                tools_used=[],   # can be enriched with actual tool names
            )
            background_tasks.add_task(send_webhook, plan)
        except Exception as e:
            log.error("persist_or_webhook_failed", error=str(e))

    return StreamingResponse(event_generator(), media_type="text/event-stream")