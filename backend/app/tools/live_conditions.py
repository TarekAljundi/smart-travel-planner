# backend/app/tools/live_conditions.py
import asyncio
import httpx
from cachetools import TTLCache
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type
)
from app.config import get_settings
from app.models.schemas import LiveConditionsInput, LiveConditionsOutput, ToolError
import structlog
from app.models.schemas import GeocodingCoords

settings = get_settings()
log = structlog.get_logger()

weather_cache = TTLCache(maxsize=500, ttl=settings.weather_cache_ttl)
weather_lock = asyncio.Lock()
geo_cache = TTLCache(maxsize=500, ttl=86400)   # 24h geocoding cache
geo_lock = asyncio.Lock()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)
async def _geocode(city: str) -> dict:
    clean_city = city.strip()
    # Apply aliases
    clean_city = settings.weather_city_aliases.get(clean_city.lower(), clean_city)

    if clean_city in geo_cache:
        return geo_cache[clean_city]

    async with geo_lock:
        if clean_city in geo_cache:
            return geo_cache[clean_city]

        coords = await _try_geocode(clean_city)
        if coords is None and "," in clean_city:
            main_city = clean_city.split(",")[0].strip()
            log.info("geocoding.retry_without_state", original=clean_city, stripped=main_city)
            coords = await _try_geocode(main_city)

        if coords is None:
            raise ValueError(f"Coordinates for '{city}' not found in geocoding database")

        geo_cache[clean_city] = coords
        return coords


async def _try_geocode(city_name: str) -> GeocodingCoords  | None:
    log.info("geocoding.lookup", city=city_name)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            settings.geocoding_api_url,
            params={"name": city_name, "count": 1, "language": "en", "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "results" not in data or len(data["results"]) == 0:
            return None
        result = data["results"][0]
        return GeocodingCoords(lat=result["latitude"], lon=result["longitude"])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)
async def _fetch_weather(city: str) -> dict:
    coords = await _geocode(city)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            settings.weather_api_url,
            params={"latitude": coords.lat,
                        "longitude": coords.lon, "current_weather": "true"},
        )
        resp.raise_for_status()
        return resp.json()


async def live_conditions(input: LiveConditionsInput) -> LiveConditionsOutput | ToolError:
    city = input.city.strip()
    if not city:
        return ToolError(error="No city provided", retryable=False)

    if city in weather_cache:
        log.info("weather.cache_hit", city=city)
        return weather_cache[city]

    async with weather_lock:
        if city in weather_cache:
            return weather_cache[city]
        log.info("weather.cache_miss", city=city)
        try:
            data = await _fetch_weather(city)
            current = data["current_weather"]
            code = current["weathercode"]
            weather_map = {
                0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
                45: "foggy", 48: "depositing rime fog", 51: "light drizzle",
                53: "moderate drizzle", 55: "dense drizzle", 61: "slight rain",
                63: "moderate rain", 65: "heavy rain", 71: "slight snow",
                73: "moderate snow", 75: "heavy snow", 95: "thunderstorm",
            }
            conditions = weather_map.get(code, f"weather code {code}")
            result = LiveConditionsOutput(
                temperature_c=current["temperature"],
                conditions=conditions,
            )
            weather_cache[city] = result
            return result
        except httpx.HTTPStatusError as e:
            return ToolError(error=f"Weather API returned {e.response.status_code}", retryable=False)
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            return ToolError(error=f"Weather API unreachable: {e}", retryable=True)
        except ValueError as e:
            return ToolError(error=str(e), retryable=False)
        except Exception as e:
            log.error("weather.unexpected_error", error=str(e))
            return ToolError(error=f"Unexpected weather error: {e}", retryable=False)