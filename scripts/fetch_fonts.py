"""Download Spectral (SIL Open Font License) as self-hosted woff2 so the app works offline."""
import os
import re

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "fonts")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
CSS = "https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,200;0,400;0,600;1,400&display=swap"

os.makedirs(OUT, exist_ok=True)
css = requests.get(CSS, headers=UA, timeout=60).text
# keep only the latin subset blocks
blocks = re.findall(r"/\* (\w[\w-]*) \*/\s*@font-face\s*{([^}]*)}", css)
for subset, body in blocks:
    if subset != "latin":
        continue
    style = re.search(r"font-style:\s*(\w+)", body).group(1)
    weight = re.search(r"font-weight:\s*(\d+)", body).group(1)
    url = re.search(r"url\((https://[^)]+\.woff2)\)", body).group(1)
    name = f"spectral-{weight}{'-italic' if style == 'italic' else ''}.woff2"
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(requests.get(url, headers=UA, timeout=60).content)
    print(name, os.path.getsize(os.path.join(OUT, name)))
