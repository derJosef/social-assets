#!/usr/bin/env python3
"""One-off, reproducible brand visual for the 2026-10-08 research smoke test.
Original brand logo is never generated or modified. The validated compositing
algorithm comes from PersonalOS and is called separately by GitHub Actions.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import os, math

W = H = 1080
OUT = Path("drafts/.visual-e2e-base.png")
OUT.parent.mkdir(parents=True, exist_ok=True)
font_file = os.environ.get("INTER_FONT", "Inter.ttf")
if not Path(font_file).is_file():
    raise RuntimeError("Inter font missing: refusing an off-brand output")
def font(size):
    return ImageFont.truetype(font_file, size)
im = Image.new("RGB", (W, H))
px = im.load()
for y in range(H):
    for x in range(W):
        t = 0.52*x/W + 0.48*y/H
        px[x,y] = (7+round(7*t), 17+round(13*t), 31+round(23*t))
d = ImageDraw.Draw(im, "RGBA")
# Quiet background grid and small, precise technical nodes.
for x in range(48, W, 48):
    d.line([(x,0),(x,H)], fill=(124,156,209,13), width=1)
for y in range(48, H, 48):
    d.line([(0,y),(W,y)], fill=(124,156,209,13), width=1)
d.rounded_rectangle((56,58,308,101), radius=21, fill=(19,35,58,255), outline=(124,156,209,110), width=2)
d.text((76,69), "KI IM BETRIEB", font=font(19), fill="#B6C4D0")
d.text((59,145), "EIN AGENT.", font=font(81), fill="#F5F7FA")
d.text((59,240), "DREI TESTS.", font=font(85), fill="#7C9CD1")
d.text((61,359), "Erst pruefen. Dann einsetzen.", font=font(33), fill="#F5F7FA")
# One continuous trace through three independently testable stages.
d.line((106,586,974,586), fill=(124,156,209,110), width=5)
cards = [
    (62, "01", "MODELLTEST", "Kann er die Aufgabe?"),
    (395, "02", "RED TEAMING", "Was passiert im Grenzfall?"),
    (728, "03", "NUTZERTEST", "Passt es zum Alltag?"),
]
for x,n,title,desc in cards:
    d.rounded_rectangle((x,474,x+289,744),radius=21,fill=(19,35,58,245),outline=(124,156,209,130),width=2)
    d.rounded_rectangle((x+19,493,x+85,555),radius=12,fill=(37,64,107,255))
    d.text((x+31,505),n,font=font(31),fill="#F5F7FA")
    d.text((x+19,621),title,font=font(26),fill="#F5F7FA")
    d.text((x+19,675),desc,font=font(17),fill="#B6C4D0")
    d.ellipse((x+126,576,x+146,596),fill="#147D78")
d.line((60,816,699,816),fill=(124,156,209,100),width=2)
d.text((60,846),"TESTEN  /  PROTOKOLLIEREN",font=font(25),fill="#F5F7FA")
d.text((60,896),"Ergebnisse statt Versprechen.",font=font(24),fill="#B6C4D0")
d.text((60,1016),"AI AGENT BUILDER  |  PRAXISREIHE",font=font(18),fill="#7C9CD1")
im.save(OUT,format="PNG",optimize=True)
print(f"BASE_IMAGE={OUT} SIZE={im.size}")
