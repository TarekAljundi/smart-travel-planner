# backend/scripts/split_docs.py
import os
import re

BASE_DIR = "knowledge_base"
HEADING_RE = re.compile(r'^=+\s*(.+?)\s*=+$', re.MULTILINE)

for dest_name in os.listdir(BASE_DIR):
    dest_dir = os.path.join(BASE_DIR, dest_name)
    if not os.path.isdir(dest_dir):
        continue

    full_path = os.path.join(dest_dir, "full.txt")
    if not os.path.exists(full_path):
        print(f"No full.txt in {dest_dir}, skipping.")
        continue

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    sections = HEADING_RE.split(content)
    intro = sections[0].strip()
    parts = []
    if intro:
        parts.append(("Overview", intro))

    for i in range(1, len(sections), 2):
        heading = sections[i].strip()
        body = sections[i+1].strip() if i+1 < len(sections) else ""
        if heading and body:
            # Create a safe filename from heading
            safe_heading = re.sub(r'[^\w\s]', '', heading).strip()[:40]
            if not safe_heading:
                safe_heading = "Section"
            parts.append((safe_heading, body))

    # Write up to 3 parts (to avoid too many tiny files)
    for section_name, text in parts[:3]:
        fname = f"{section_name}.txt".replace(" ", "_")
        out_path = os.path.join(dest_dir, fname)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  Wrote {out_path}")

    # Remove full.txt to avoid re‑processing
    os.remove(full_path)
    print(f"Processed {dest_name}")