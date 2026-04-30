# backend/scripts/fetch_wikivoyage.py
import requests
import re
import os

DESTINATIONS = {
    "Paris": "Paris",
    "Tokyo": "Tokyo",
    "Bali": "Bali",
    "Swiss Alps": "Swiss_Alps",
    "Santorini": "Santorini",
    "Machu Picchu": "Machu_Picchu",
    "New York City": "New_York_City",
    "Cape Town": "Cape_Town",
    "Queenstown": "Queenstown_(New_Zealand)",
    "Costa Rica": "Costa_Rica",
    "Amalfi Coast": "Amalfi_Coast",
    "Zanzibar": "Zanzibar",
}

BASE_DIR = "knowledge_base"
os.makedirs(BASE_DIR, exist_ok=True)

def fetch_raw(page_title: str) -> str:
    url = f"https://en.wikivoyage.org/w/index.php?title={page_title}&action=raw"
    resp = requests.get(url, headers={"User-Agent": "SmartTravelPlanner/1.0"})
    resp.raise_for_status()
    return resp.text

def clean_wikitext(raw: str) -> str:
    # Same cleaning as before (kept unchanged for brevity)
    text = re.sub(r'\{\{.*?\}\}', '', raw, flags=re.DOTALL)
    text = re.sub(r'<.*?>', '', text)
    text = re.sub(r'\{\|.*?\|\}', '', text, flags=re.DOTALL)
    text = re.sub(r"'''?", '', text)
    text = re.sub(r'<ref.*?>.*?</ref>', '', text, flags=re.DOTALL)
    text = re.sub(r'\[https?://[^\s]+\s+([^\]]+)\]', r'\1', text)
    def replace_link(m):
        inner = m.group(1)
        if '|' in inner:
            return inner.split('|')[-1]
        return inner
    text = re.sub(r'\[\[([^\]]+)\]\]', replace_link, text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

for dest, page in DESTINATIONS.items():
    print(f"Fetching {dest} ...")
    raw = fetch_raw(page)
    clean = clean_wikitext(raw)

    dest_folder = os.path.join(BASE_DIR, dest)
    os.makedirs(dest_folder, exist_ok=True)

    # Save the full raw text as 'full.txt' (will be split later)
    filepath = os.path.join(dest_folder, "full.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(clean)
    print(f"Saved {filepath}")