# backend/tests/test_tools.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import numpy as np
from app.tools.rag_search import rag_search
from app.tools.classify_destination import classify_destination
from app.tools.live_conditions import live_conditions, weather_cache
from app.models.schemas import (
    RAGQuery,
    ClassifyInput,
    LiveConditionsInput,
    LiveConditionsOutput,
    ToolError,
    DestinationFeatures,
)

# ---------------------- RAG search tool ----------------------
@pytest.mark.asyncio
async def test_rag_search_returns_results(async_session):
    query = RAGQuery(query="test")
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        ("Paris", "Eiffel Tower is famous", 0.95),
        ("Paris", "Louvre museum", 0.80),
    ]
    mock_embedder = MagicMock()
    # Return a NumPy array (like the real SentenceTransformer)
    mock_embedder.encode.return_value = np.array([0.1, 0.2, 0.3])

    with patch.object(async_session, "execute", return_value=mock_result):
        results = await rag_search(query, async_session, mock_embedder, top_k=2)
        assert len(results) == 2
        assert results[0].destination == "Paris"

@pytest.mark.asyncio
async def test_rag_search_returns_empty(async_session):
    query = RAGQuery(query="unknown")
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = np.array([0.1, 0.2, 0.3])

    with patch.object(async_session, "execute", return_value=mock_result):
        results = await rag_search(query, async_session, mock_embedder, top_k=2)
        assert len(results) == 1
        assert "No information found" in results[0].text

# ---------------------- Classify tool ----------------------
@pytest.mark.asyncio
async def test_classify_destination_returns_label():
    mock_classifier = MagicMock()
    mock_classifier.predict.return_value = ["Adventure"]
    mock_classifier.predict_proba.return_value = [[0.1, 0.2, 0.3, 0.1, 0.1, 0.2]]
    mock_classifier.classes_ = ["Adventure", "Relaxation", "Culture", "Budget", "Luxury", "Family"]

    features = DestinationFeatures(
        continent="Europe",
        avg_temperature=15.0,
        cost_index=50,
        hiking_score=9.0,
        beach_score=1.0,
        culture_score=5.0,
        family_friendly_score=5.0,
        tourist_density=4.0,
    )
    inp = ClassifyInput(features=features)
    out = await classify_destination(inp, mock_classifier)
    assert out.label == "Adventure"
    assert "Adventure" in out.probabilities

# ---------------------- Weather tool ----------------------
@pytest.mark.asyncio
async def test_live_conditions_success():
    input = LiveConditionsInput(city="Paris")
    with patch("app.tools.live_conditions._fetch_weather", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {
            "current_weather": {"temperature": 22.0, "weathercode": 1}
        }
        result = await live_conditions(input)
        assert isinstance(result, LiveConditionsOutput)
        assert result.temperature_c == 22.0
        assert result.conditions == "mainly clear"

@pytest.mark.asyncio
async def test_live_conditions_timeout_returns_tool_error():
    weather_cache.clear()
    input = LiveConditionsInput(city="Paris")
    with patch("app.tools.live_conditions._fetch_weather", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = httpx.TimeoutException("timeout")
        result = await live_conditions(input)
        assert isinstance(result, ToolError)
        assert result.retryable is True