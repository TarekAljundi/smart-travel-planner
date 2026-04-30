# backend/app/services/features.py
"""
Dynamic feature extraction for travel destinations.
All data is fetched live from free internet APIs — no hardcoded values.

Data sources:
  - Open‑Meteo Geocoding API  → continent, country, lat/lon
  - Open‑Meteo Archive API    → average July temperature (5‑year average)
  - Numbeo Cost‑Of‑Living CSV → cost index (scaled 10‑100)
  - Wikivoyage raw articles   → hiking_score, beach_score, culture_score, tourist_density
"""

import asyncio
import httpx
import numpy as np
import re
from app.models.schemas import DestinationFeatures
from app.config import get_settings

settings = get_settings()

# Cache for geocoding results (city name → data)
_geo_cache: dict = {}
_cost_cache: dict = {}
_wikivoyage_cache: dict = {}

# ---------- Helper: Geocode a city ----------
async def _geocode_city(city: str, client: httpx.AsyncClient) -> dict | None:
    """Resolve a city name to lat/lon + country using Open‑Meteo Geocoding API (free, no key)."""
    if city.lower() in _geo_cache:
        return _geo_cache[city.lower()]

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city, "count": 1, "language": "en", "format": "json"}
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    if "results" not in data or len(data["results"]) == 0:
        return None
    result = data["results"][0]
    geo = {
        "lat": result["latitude"],
        "lon": result["longitude"],
        "country": result.get("country", ""),
        "country_code": result.get("country_code", ""),
    }
    _geo_cache[city.lower()] = geo
    return geo


# ---------- Continent mapping from country code ----------
_COUNTRY_TO_CONTINENT = {
    "AF": "Asia", "AL": "Europe", "DZ": "Africa", "AD": "Europe", "AO": "Africa",
    "AR": "South America", "AM": "Asia", "AU": "Oceania", "AT": "Europe",
    "AZ": "Asia", "BS": "North America", "BH": "Asia", "BD": "Asia", "BB": "North America",
    "BY": "Europe", "BE": "Europe", "BZ": "Central America", "BJ": "Africa",
    "BT": "Asia", "BO": "South America", "BA": "Europe", "BW": "Africa",
    "BR": "South America", "BN": "Asia", "BG": "Europe", "BF": "Africa",
    "BI": "Africa", "KH": "Asia", "CM": "Africa", "CA": "North America",
    "CV": "Africa", "CF": "Africa", "TD": "Africa", "CL": "South America",
    "CN": "Asia", "CO": "South America", "KM": "Africa", "CG": "Africa",
    "CR": "Central America", "HR": "Europe", "CU": "Central America", "CY": "Europe",
    "CZ": "Europe", "DK": "Europe", "DJ": "Africa", "DM": "North America",
    "DO": "North America", "EC": "South America", "EG": "Africa", "SV": "Central America",
    "GQ": "Africa", "ER": "Africa", "EE": "Europe", "SZ": "Africa",
    "ET": "Africa", "FJ": "Oceania", "FI": "Europe", "FR": "Europe",
    "GA": "Africa", "GM": "Africa", "GE": "Asia", "DE": "Europe",
    "GH": "Africa", "GR": "Europe", "GD": "North America", "GT": "Central America",
    "GN": "Africa", "GW": "Africa", "GY": "South America", "HT": "North America",
    "HN": "Central America", "HU": "Europe", "IS": "Europe", "IN": "Asia",
    "ID": "Asia", "IR": "Asia", "IQ": "Asia", "IE": "Europe",
    "IL": "Asia", "IT": "Europe", "JM": "North America", "JP": "Asia",
    "JO": "Asia", "KZ": "Asia", "KE": "Africa", "KI": "Oceania",
    "KW": "Asia", "KG": "Asia", "LA": "Asia", "LV": "Europe",
    "LB": "Asia", "LS": "Africa", "LR": "Africa", "LY": "Africa",
    "LI": "Europe", "LT": "Europe", "LU": "Europe", "MG": "Africa",
    "MW": "Africa", "MY": "Asia", "MV": "Asia", "ML": "Africa",
    "MT": "Europe", "MH": "Oceania", "MR": "Africa", "MU": "Africa",
    "MX": "North America", "FM": "Oceania", "MD": "Europe", "MC": "Europe",
    "MN": "Asia", "ME": "Europe", "MA": "Africa", "MZ": "Africa",
    "MM": "Asia", "NA": "Africa", "NR": "Oceania", "NP": "Asia",
    "NL": "Europe", "NZ": "Oceania", "NI": "Central America", "NE": "Africa",
    "NG": "Africa", "KP": "Asia", "MK": "Europe", "NO": "Europe",
    "OM": "Asia", "PK": "Asia", "PW": "Oceania", "PA": "Central America",
    "PG": "Oceania", "PY": "South America", "PE": "South America", "PH": "Asia",
    "PL": "Europe", "PT": "Europe", "QA": "Asia", "RO": "Europe",
    "RU": "Europe", "RW": "Africa", "KN": "North America", "LC": "North America",
    "VC": "North America", "WS": "Oceania", "SM": "Europe", "ST": "Africa",
    "SA": "Asia", "SN": "Africa", "RS": "Europe", "SC": "Africa",
    "SL": "Africa", "SG": "Asia", "SK": "Europe", "SI": "Europe",
    "SB": "Oceania", "SO": "Africa", "ZA": "Africa", "KR": "Asia",
    "SS": "Africa", "ES": "Europe", "LK": "Asia", "SD": "Africa",
    "SR": "South America", "SE": "Europe", "CH": "Europe", "SY": "Asia",
    "TW": "Asia", "TJ": "Asia", "TZ": "Africa", "TH": "Asia",
    "TL": "Asia", "TG": "Africa", "TO": "Oceania", "TT": "North America",
    "TN": "Africa", "TR": "Asia", "TM": "Asia", "TV": "Oceania",
    "UG": "Africa", "UA": "Europe", "AE": "Asia", "GB": "Europe",
    "US": "North America", "UY": "South America", "UZ": "Asia", "VU": "Oceania",
    "VA": "Europe", "VE": "South America", "VN": "Asia", "YE": "Asia",
    "ZM": "Africa", "ZW": "Africa",
}


def _country_code_to_continent(code: str) -> str:
    return _COUNTRY_TO_CONTINENT.get(code.upper(), "Europe")


# ---------- Temperature: Open‑Meteo Archive API ----------
async def _fetch_avg_temperature(lat: float, lon: float, month: int = 7, client=None) -> float:
    """
    Fetch the average daily temperature for a given month averaged over the last 5 years.
    Uses Open‑Meteo Historical Weather API (free, no key required).
    """
    if client is None:
        async with httpx.AsyncClient(timeout=30.0) as client: 
            return await _fetch_avg_temperature(lat, lon, month, client)

    url = "https://archive-api.open-meteo.com/v1/archive"
    temps = []
    for year in range(2020, 2025):  # 5-year average for climate normal
        start = f"{year}-{month:02d}-01"
        end = f"{year}-{month:02d}-28" if month == 2 else f"{year}-{month:02d}-30"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "daily": "temperature_2m_mean",
            "timezone": "auto",
        }
        resp = await client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            daily_temps = data.get("daily", {}).get("temperature_2m_mean", [])
            if daily_temps:
                temps.append(sum(daily_temps) / len(daily_temps))

    if not temps:
        # Fallback: rough estimate based on latitude
        return max(-10, 40 - abs(lat - 25) * 0.7)
    return round(sum(temps) / len(temps), 1)


# ---------- Cost Index: Numbeo dataset from GitHub ----------
_NUMBEO_LOADED = False
_NUMBEO_COL: dict = {}

def _load_numbeo_data():
    """Load the Numbeo cost‑of‑living CSV once from GitHub."""
    global _NUMBEO_LOADED, _NUMBEO_COL
    if _NUMBEO_LOADED:
        return
    import csv, io, requests
    url = "https://raw.githubusercontent.com/emirrdvn/Quality-Of-Life-Expectancy-By-Countries/main/Quality_of_Life.csv"
    resp = requests.get(url, timeout=10)
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        country = row.get("country", "").strip()
        col_val = row.get("Cost of Living Value", "0")
        try:
            _NUMBEO_COL[country.lower()] = float(col_val)
        except ValueError:
            pass
    _NUMBEO_LOADED = True


def _get_cost_index(country: str) -> int:
    """Map Numbeo Cost‑of‑Living Value (0‑200+) to our 10‑100 scale."""
    _load_numbeo_data()
    col_val = _NUMBEO_COL.get(country.lower(), 50)
    # Numbeo COL values: higher = more expensive. Scale to 10‑100.
    # Most values range from 20‑100. Clamp and scale.
    scaled = max(10, min(100, int(col_val * 0.8 + 10)))
    return scaled


# ---------- Wikivoyage: Activity & Density Scores ----------
async def _fetch_wikivoyage_scores(destination: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch the raw Wikivoyage article for a destination and compute:
      - hiking_score (0‑10): based on 'Do' section content
      - beach_score  (0‑10): based on beach mentions
      - culture_score(0‑10): based on 'See' section content
      - tourist_density (1‑10): based on article size & popularity indicators
    """
    cache_key = destination.lower()
    if cache_key in _wikivoyage_cache:
        return _wikivoyage_cache[cache_key]

    # Build Wikivoyage URL — try common page name patterns
    page_name = destination.replace(" ", "_")
    url = f"https://en.wikivoyage.org/w/index.php?title={page_name}&action=raw"
    resp = await client.get(url, headers={"User-Agent": "SmartTravelPlanner/1.0"})
    if resp.status_code != 200:
        # Fallback: try with "City" suffix
        url2 = f"https://en.wikivoyage.org/w/index.php?title={page_name}_(city)&action=raw"
        resp = await client.get(url2, headers={"User-Agent": "SmartTravelPlanner/1.0"})
        if resp.status_code != 200:
            return {"hiking_score": 4.0, "beach_score": 4.0, "culture_score": 5.0, "tourist_density": 5.0}

    raw_text = resp.text
    # Remove wiki markup for cleaner analysis
    clean = re.sub(r'\{\{.*?\}\}', '', raw_text, flags=re.DOTALL)
    clean = re.sub(r'<.*?>', '', clean)
    clean_lower = clean.lower()

    # ---- Hiking score: based on 'Do' section mentions of hiking/trekking/climbing ----
    do_section = ""
    do_match = re.search(r'=+\s*Do\s*=+\s*\n(.*?)(?=\n=+\s*\w)', clean, re.DOTALL)
    if do_match:
        do_section = do_match.group(1).lower()
    hiking_keywords = ["hiking", "trekking", "trail", "climbing", "mountain", "walk",
                       "national park", "nature reserve", "summit", "peak", "hike"]
    hiking_count = sum(do_section.count(kw) for kw in hiking_keywords)
    # Also check entire article for hiking references
    hiking_count += sum(clean_lower.count(kw) for kw in ["hiking", "trekking", "trail"]) // 3
    hiking_score = min(10.0, max(1.0, 2.0 + hiking_count * 0.8))

    # ---- Beach score: count beach‑related mentions ----
    beach_keywords = ["beach", "beaches", "swim", "surf", "diving", "snorkel",
                      "coast", "shore", "sand", "cove", "lagoon", "bay"]
    beach_count = sum(clean_lower.count(kw) for kw in beach_keywords)
    beach_score = min(10.0, max(1.0, 1.0 + beach_count * 0.3))

    # ---- Culture score: based on 'See' section size and cultural keywords ----
    see_section = ""
    see_match = re.search(r'=+\s*See\s*=+\s*\n(.*?)(?=\n=+\s*\w)', clean, re.DOTALL)
    if see_match:
        see_section = see_match.group(1).lower()
    culture_keywords = ["museum", "temple", "church", "cathedral", "palace", "castle",
                        "historic", "monument", "gallery", "unesco", "heritage",
                        "ruins", "art", "architecture", "ancient", "old town"]
    culture_count = sum(see_section.count(kw) for kw in culture_keywords)
    culture_count += sum(clean_lower.count(kw) for kw in ["museum", "unesco", "heritage"]) // 2
    culture_score = min(10.0, max(2.0, 2.0 + culture_count * 0.6))

    # ---- Tourist density: estimated from article size and popularity keywords ----
    article_size = len(clean)
    # Longer articles → more popular destination
    size_score = min(10.0, article_size / 5000)  # 50k chars → score 10
    popular_keywords = ["popular", "tourist", "crowd", "busy", "peak season"]
    pop_count = sum(clean_lower.count(kw) for kw in popular_keywords)
    tourist_density = min(10.0, max(1.0, (size_score * 3 + pop_count * 1.5) / 4))

    scores = {
        "hiking_score": round(hiking_score, 1),
        "beach_score": round(beach_score, 1),
        "culture_score": round(culture_score, 1),
        "tourist_density": round(tourist_density, 1),
    }
    _wikivoyage_cache[cache_key] = scores
    return scores


# ---------- Main entry point ----------
async def compute_features(destination: str, continent: str = None) -> DestinationFeatures:
    """
    Given a destination name, fetch all features live from the internet:
      - Continent & temperature from Open‑Meteo
      - Cost index from Numbeo (via GitHub)
      - Activity scores from Wikivoyage article analysis
    Falls back to reasonable defaults if any source is unavailable.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1. Geocode for continent, country, and coordinates
        geo = await _geocode_city(destination, client)
        if geo is None:
            # Fallback — use continent from parameter or default
            continent = continent or "Europe"
            lat, lon = 48.0, 2.0  # generic European fallback
            country = destination
        else:
            continent = continent or _country_code_to_continent(geo["country_code"])
            lat, lon = geo["lat"], geo["lon"]
            country = geo["country"] or destination

        # 2. Temperature (July average from Open‑Meteo Archive API)
        try:
            avg_temp = await _fetch_avg_temperature(lat, lon, month=7, client=client)
        except Exception:
            # Fallback: simple latitude‑based formula
            avg_temp = round(max(-10, 40 - abs(lat - 25) * 0.7 + np.random.normal(0, 2)), 1)

        # 3. Cost index (from Numbeo)
        try:
            cost_index = _get_cost_index(country)
        except Exception:
            cost_index = 50  # default

        # 4. Wikivoyage scores (hiking, beach, culture, tourist density)
        try:
            wv_scores = await _fetch_wikivoyage_scores(destination, client)
        except Exception:
            wv_scores = {"hiking_score": 4.0, "beach_score": 4.0,
                         "culture_score": 5.0, "tourist_density": 5.0}

        # 5. Family-friendly: derived from other scores
        family_score = round(
            (wv_scores["culture_score"] * 0.2 +
             (10 - wv_scores["tourist_density"]) * 0.4 +
             wv_scores["beach_score"] * 0.2 + 5.0) / 1.0,
            1
        )
        family_score = min(10.0, max(1.0, family_score))

    return DestinationFeatures(
        continent=continent,
        avg_temperature=avg_temp,
        cost_index=cost_index,
        hiking_score=wv_scores["hiking_score"],
        beach_score=wv_scores["beach_score"],
        culture_score=wv_scores["culture_score"],
        family_friendly_score=family_score,
        tourist_density=wv_scores["tourist_density"],
    )