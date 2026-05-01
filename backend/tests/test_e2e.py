# backend/tests/test_e2e.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from app.services.agent import run_agent_and_stream_synthesis
from app.models.schemas import ClassifyOutput, LiveConditionsOutput
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

@pytest.mark.asyncio
async def test_agent_stream_with_mocks():
    # 1) Mock classifier
    mock_classifier = MagicMock()
    mock_classifier.predict.return_value = ["Adventure"]
    mock_classifier.predict_proba.return_value = [[0.1, 0.2, 0.3, 0.1, 0.1, 0.2]]
    mock_classifier.classes_ = ["Adventure", "Relaxation", "Culture", "Budget", "Luxury", "Family"]

    # 2) Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = [0.1, 0.2, 0.3]

    # 3) Mock session and factory
    mock_session = AsyncMock()
    mock_session_factory = AsyncMock(return_value=mock_session)

    # 4) Mock the weather API
    with patch("app.tools.live_conditions._fetch_weather", new_callable=AsyncMock) as mock_weather:
        mock_weather.return_value = {
            "current_weather": {"temperature": 14.5, "weathercode": 0}
        }

        # 5) Mock the agent’s create_agent to return a fake that produces a pre‑canned result
        fake_agent_result = {
            "messages": [
                HumanMessage(content="Plan a trip to Queenstown"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "search_destinations", "args": {"query": "Queenstown"}, "id": "1"},
                        {"name": "classify_destination", "args": {"destination": "Queenstown"}, "id": "2"},
                        {"name": "get_weather", "args": {"city": "Queenstown"}, "id": "3"},
                    ],
                ),
                ToolMessage(
                    content=json.dumps([{"text": "Queenstown", "destination": "Queenstown", "relevance": 0.95}]),
                    tool_call_id="1"
                ),
                ToolMessage(
                    content=ClassifyOutput(label="Adventure", probabilities={"Adventure": 0.5, "Relaxation": 0.2, "Culture": 0.1, "Budget": 0.1, "Luxury": 0.05, "Family": 0.05}).model_dump_json(),
                    tool_call_id="2"
                ),
                ToolMessage(
                    content=LiveConditionsOutput(temperature_c=14.5, conditions="clear sky").model_dump_json(),
                    tool_call_id="3"
                ),
            ]
        }

        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value=fake_agent_result)

        # Mock the strong LLM's astream to yield one token
        class FakeChunk:
            content = "This is a test trip plan."

        async def fake_astream(*args, **kwargs):
            yield FakeChunk()

        mock_strong_llm = MagicMock()
        mock_strong_llm.astream = fake_astream

        with patch("app.services.agent.create_agent", return_value=mock_agent), \
             patch("app.services.agent.ChatOpenAI") as mock_chat:
            # Make the strong ChatOpenAI return our mock
            mock_chat.return_value = mock_strong_llm

            events = []
            async for sse_data in run_agent_and_stream_synthesis(
                query="Plan a trip to Queenstown",
                classifier=mock_classifier,
                embedder=mock_embedder,
                session_factory=mock_session_factory,
            ):
                events.append(sse_data)

            tool_call_events = [e for e in events if '"type": "tool_call"' in e]
            tool_result_events = [e for e in events if '"type": "tool_result"' in e]
            token_events = [e for e in events if '"type": "token"' in e]

            assert len(tool_call_events) == 3
            assert len(tool_result_events) == 3
            assert len(token_events) == 1
            assert "test trip plan" in token_events[0]  