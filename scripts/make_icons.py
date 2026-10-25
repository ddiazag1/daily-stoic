"""Render the app icons: an incised serif 'S' on verdigris, framed like a carved tablet."""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "icons")
os.makedirs(OUT, exist_ok=True)

STONE = (230, 230, 225)
VERD = (43, 106, 94)
VERD_DARK = (31, 82, 72)
FONT_CANDIDATES = [r"C:\Windows\Fonts\pala.ttf", r"C:\Windows\Fonts\georgia.ttf", r"C:\Windows\Fonts\times.ttf"]
FONT = next(p for p in FONT_CANDIDATES if os.path.exists(p))


def render(size: int, pad_ratio: float = 0.0) -> Image.Image:
    s = size * 4  # supersample
    img = Image.new("RGB", (s, s), VERD)
    d = ImageDraw.Draw(img)
    # subtle vertical tone, lighter at top like light falling on stone
    for y in range(s):
        t = y / s
        c = tuple(int(VERD[i] * (1 - t * 0.18) + VERD_DARK[i] * (t * 0.18)) for i in range(3))
        d.line([(0, y), (s, y)], fill=c)
    inset = int(s * (0.09 + pad_ratio))
    d.rectangle([inset, inset, s - inset, s - inset], outline=STONE + (0,), width=max(2, s // 160))
    font = ImageFont.truetype(FONT, int(s * (0.60 - pad_ratio * 1.2)))
    text = "S"
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (s - w) / 2 - bbox[0], (s - h) / 2 - bbox[1]
    # incised letter: dark upper cut + light lower lip, then the stone face
    shadow = Image.new("L", (s, s), 0)
    ImageDraw.Draw(shadow).text((x, y - s * 0.006), text, font=font, fill=150)
    img.paste((18, 52, 46), mask=shadow.filter(ImageFilter.GaussianBlur(s * 0.004)))
    hi = Image.new("L", (s, s), 0)
    ImageDraw.Draw(hi).text((x, y + s * 0.006), text, font=font, fill=120)
    img.paste((150, 196, 184), mask=hi)
    d.text((x, y), text, font=font, fill=STONE)
    return img.resize((size, size), Image.LANCZOS)


for size, name, pad in [(192, "icon-192.png", 0), (512, "icon-512.png", 0),
                        (512, "icon-maskable-512.png", 0.08), (180, "apple-touch-icon.png", 0)]:
    render(size, pad).save(os.path.join(OUT, name), optimize=True)
    print(name)

svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="12" fill="#2b6a5e"/>
<rect x="6" y="6" width="52" height="52" rx="3" fill="none" stroke="#e6e6e1" stroke-opacity=".55" stroke-width="1"/>
<text x="32" y="45" text-anchor="middle" font-family="Palatino, 'Palatino Linotype', Georgia, serif" font-size="38" fill="#e6e6e1">S</text>
</svg>
"""
with open(os.path.join(OUT, "icon.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("icon.svg")
