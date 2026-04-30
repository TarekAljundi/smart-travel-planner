# backend/tests/test_tools.py
import pytest
from unittest.mock import AsyncMock, patch
from app.tools.live_conditions import live_conditions, ToolError
from app.models.schemas import LiveConditionsInput

@pytest.mark.asyncio
async def test_live_conditions_success():
    input = LiveConditionsInput(city="Paris")
    # Mock _fetch_weather
    with patch("app.tools.live_conditions._fetch_weather", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"current_weather": {"temperature": 22.0, "weathercode": 1}}
        result = await live_conditions(input)
        assert result.temperature_c == 22.0
        assert result.conditions == "1"

@pytest.mark.asyncio
async def test_live_conditions_timeout_returns_tool_error():
    input = LiveConditionsInput(city="Paris")
    with patch("app.tools.live_conditions._fetch_weather", new_callable=AsyncMock) as mock_fetch:
        import httpx
        mock_fetch.side_effect = httpx.TimeoutException("timeout")
        result = await live_conditions(input)
        assert isinstance(result, ToolError)
        assert result.retryable is True