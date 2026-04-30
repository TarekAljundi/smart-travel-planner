# backend/ml/generate_dataset.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import os
import traceback
import numpy as np
import pandas as pd
from app.services.features import compute_features
from app.config import get_settings
from app.models.schemas import DestinationFeatures

settings = get_settings()

# ---------- Destination list (unchanged) ----------
DESTINATION_NAMES = [
    "Paris", "Tokyo", "Bali", "Swiss Alps", "Santorini", "Machu Picchu",
    "New York City", "Cape Town", "Queenstown", "Costa Rica", "Amalfi Coast",
    "Zanzibar", "Yellowstone", "Banff", "Patagonia", "Sahara Desert",
    "Great Barrier Reef", "Venice", "Barcelona", "Phuket", "Cinque Terre",
    "Victoria Falls", "Galápagos", "Serengeti", "Aspen", "Edinburgh",
    "Florence", "Granada", "Hanoi", "Istanbul", "Jaipur",
    "Kruger National Park", "Lisbon", "Marrakech", "Nashville",
    "Oslo", "Porto", "Riviera Maya", "San Francisco", "Tahiti",
    "Ubud", "Vienna", "Whistler", "Bora Bora", "Cairo", "Dublin",
    "Easter Island", "Fiji", "Geneva", "Helsinki", "Ibiza",
    "Jerusalem", "Kathmandu", "London", "Maui", "Nice", "Orlando",
    "Petra", "Québec City", "Rome", "Shanghai", "Tulum", "Vancouver",
    "Washington D.C.", "Xi'an", "Yosemite", "Zurich", "Athens",
    "Berlin", "Budapest", "Buenos Aires", "Copenhagen", "Delhi",
    "Dubrovnik", "Gran Canaria", "Havana", "Koh Samui", "La Paz",
    "Madrid", "Moscow", "Nairobi", "Osaka", "Prague", "Reykjanes",
    "Seoul", "Tallinn", "Ushuaia", "Valletta", "Warsaw", "Antarctica",
    "Sapporo", "Bogota", "Lima", "Salt Lake City", "Chicago",
    "Houston", "Miami", "Las Vegas", "Toronto", "Montreal",
    "Melbourne", "Auckland", "Christchurch", "Cusco", "La Fortuna",
    "Bangkok", "Kuala Lumpur", "Singapore", "Hong Kong", "Taipei",
    "Manila", "Seville", "Valencia", "Bilbao", "Split", "Zagreb",
    "Ljubljana", "Bratislava", "Riga", "Vilnius", "Santiago",
    "Quito", "Medellín", "Cartagena", "Montevideo", "Asunción",
    "Paramaribo", "Anchorage", "Honolulu", "Juneau", "Fairbanks",
    "Siem Reap", "Vientiane", "Yangon", "Colombo", "Kathmandu",
    "Thimphu", "Muscat", "Amman", "Beirut",
]

TARGET_ROWS = 1000

# ---------- Fallback geocoding data (latitude, continent) ----------
FALLBACK_LAT = {
    "Aspen": 39.19, "Edinburgh": 55.95, "Nashville": 36.16, "Oslo": 59.91,
    "Porto": 41.15, "Riviera Maya": 20.62, "San Francisco": 37.77, "Tahiti": -17.65,
    "Geneva": 46.20, "Helsinki": 60.17, "Ibiza": 38.91, "Jerusalem": 31.77,
    "Kathmandu": 27.71, "Maui": 20.80, "Québec City": 46.81, "Rome": 41.90,
    "Xi'an": 34.26, "Zurich": 47.38, "Athens": 37.98, "Budapest": 47.50,
    "Buenos Aires": -34.60, "Dubrovnik": 42.65, "Gran Canaria": 28.10,
    "Koh Samui": 9.50, "Madrid": 40.42, "Moscow": 55.75, "Prague": 50.08,
    "Reykjanes": 63.95, "Seoul": 37.57, "Ushuaia": -54.80, "Antarctica": -82.5,
    "Salt Lake City": 40.76, "Chicago": 41.88, "Montreal": 45.50,
    "Auckland": -36.85, "Cusco": -13.52, "La Fortuna": 10.47,
    "Kuala Lumpur": 3.13, "Singapore": 1.35, "Hong Kong": 22.30,
    "Taipei": 25.03, "Seville": 37.39, "Valencia": 39.47,
    "Ljubljana": 46.05, "Bratislava": 48.15, "Quito": -0.18,
    "Asunción": -25.30, "Anchorage": 61.22, "Honolulu": 21.31,
    "Vientiane": 17.97, "Colombo": 6.93, "Muscat": 23.61, "Beirut": 33.89,
}

def get_continent(lat):
    if lat > 50: return "Europe"
    if lat < -20: return "Oceania" if abs(lat) > 35 else "South America"
    if lat < 10:  return "Africa" if lat > -20 else "Asia"
    if lat < 30:  return "Central America"
    if lat < 45:  return "North America" if abs(lat) < 40 else "Europe"
    return "Europe"

def fallback_features(dest):
    lat = FALLBACK_LAT.get(dest, 48.0)
    avg_temp = round(max(-10, 40 - abs(lat - 25) * 0.7 + np.random.normal(0, 2)), 1)
    continent = get_continent(lat)
    return DestinationFeatures(
        continent=continent,
        avg_temperature=avg_temp,
        cost_index=50,
        hiking_score=4.0,
        beach_score=4.0,
        culture_score=5.0,
        family_friendly_score=5.0,
        tourist_density=5.0,
    )

# ---------- Fetch with fallback ----------
async def fetch_one(name, sem):
    async with sem:
        try:
            feat = await compute_features(name)
            return name, feat
        except Exception as e:
            # Just print a short warning, no stack trace
            print(f"  Using fallback for {name}: {type(e).__name__} - {e}")
            return name, fallback_features(name)

async def fetch_base_features(names):
    sem = asyncio.Semaphore(1)   # sequential to avoid rate limits
    tasks = [fetch_one(name, sem) for name in names]
    results = await asyncio.gather(*tasks)
    base = {}
    for name, feat in results:
        base[name] = feat
    return base

# ---------- Noise, labeling, and main generator unchanged ----------
def add_noise(features, seed=None):
    if seed is not None:
        np.random.seed(seed)
    noisy = features.model_dump()
    noisy["avg_temperature"] = round(noisy["avg_temperature"] + np.random.normal(0, 1.5), 1)
    noisy["cost_index"] = int(max(10, min(100, noisy["cost_index"] + np.random.normal(0, 4))))
    for col in ["hiking_score", "beach_score", "culture_score",
                "family_friendly_score", "tourist_density"]:
        noisy[col] = round(max(0.0, min(10.0, noisy[col] + np.random.normal(0, 0.4))), 1)
    return noisy

def assign_label(row):
    if row["cost_index"] <= 35:
        return "Budget"
    if row["cost_index"] >= 80:
        return "Luxury"
    if row["hiking_score"] >= 7 and row["beach_score"] <= 4:
        return "Adventure"
    if row["beach_score"] >= 7 and row["tourist_density"] <= 7:
        return "Relaxation"
    if row["culture_score"] >= 8 and row["tourist_density"] >= 4:
        return "Culture"
    if row["family_friendly_score"] >= 7 and row["tourist_density"] <= 7:
        return "Family"
    scores = {
        "Adventure": row["hiking_score"],
        "Relaxation": row["beach_score"],
        "Culture": row["culture_score"],
        "Family": row["family_friendly_score"],
    }
    return max(scores, key=scores.get)

async def generate_dataset():
    print(f"Fetching base features for {len(DESTINATION_NAMES)} unique destinations...")
    base_features = await fetch_base_features(DESTINATION_NAMES)
    print(f"Successfully fetched {len(base_features)} destinations.")

    copies_per = TARGET_ROWS // len(base_features) + 1
    rows = []
    np.random.seed(42)
    for dest, feat in base_features.items():
        orig_row = feat.model_dump()
        orig_row["destination"] = dest
        rows.append(orig_row)
        for i in range(copies_per - 1):
            noisy = add_noise(feat, seed=hash(dest + str(i)) % (2**31))
            noisy["destination"] = dest
            rows.append(noisy)
    rows = rows[:TARGET_ROWS]

    df = pd.DataFrame(rows)
    df["label"] = df.apply(assign_label, axis=1)

    # Ensure all labels present
    all_labels = ["Adventure", "Relaxation", "Culture", "Budget", "Luxury", "Family"]
    missing = [l for l in all_labels if l not in df["label"].values]
    if missing:
        print(f"Missing labels: {missing}. Forcing appropriate rows.")
        for lbl in missing:
            if lbl == "Budget":
                mask = df["cost_index"] <= 35
            elif lbl == "Luxury":
                mask = df["cost_index"] >= 80
            elif lbl == "Adventure":
                mask = df["hiking_score"] >= 7
            elif lbl == "Relaxation":
                mask = df["beach_score"] >= 7
            elif lbl == "Culture":
                mask = df["culture_score"] >= 8
            elif lbl == "Family":
                mask = df["family_friendly_score"] >= 7
            candidates = df[mask]
            if len(candidates) > 0:
                df.loc[candidates.index[0], "label"] = lbl
            else:
                df.loc[0, "label"] = lbl

    os.makedirs("data", exist_ok=True)
    output_path = "data/destinations.csv"
    df.to_csv(output_path, index=False)
    print(f"Dataset saved to {output_path} with {len(df)} rows.")
    print("Label distribution:\n", df["label"].value_counts())


if __name__ == "__main__":
    print("Generating 1000‑row dataset (this may take a few minutes even with fallbacks)...")
    asyncio.run(generate_dataset())