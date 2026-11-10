"""Profile picture + banner for the channel. Usage: python3 make_brand.py "ODDLY PROVEN" out_dir"""
import sys, os, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

NAME = sys.argv[1] if len(sys.argv) > 1 else "ODDLY PROVEN"
OUT = sys.argv[2] if len(sys.argv) > 2 else "."
os.makedirs(OUT, exist_ok=True)
F = "/usr/share/fonts/opentype/inter/"
NAVY1, NAVY2 = (11, 18, 40), (20, 38, 80)
AMBER, TEAL, WHITE = (247, 168, 37), (45, 212, 191), (245, 247, 252)
S = 3  # supersampling


def font(name, size):
    return ImageFont.truetype(F + name, size)


def bg(w, h, seed=1):
    img = Image.new("RGB", (w, h), NAVY1)
    px = img.load()
    cx, cy = w * 0.35, h * 0.3
    md = math.hypot(w, h)
    for y in range(0, h):
        for x in range(0, w, 1):
            d = math.hypot(x - cx, y - cy) / md
            t = max(0, 1 - d * 1.6)
            px[x, y] = tuple(int(NAVY1[i] + (NAVY2[i] - NAVY1[i]) * t) for i in range(3))
    return img


def glow(layer, radius):
    g = layer.filter(ImageFilter.GaussianBlur(radius))
    return Image.alpha_composite(g, layer)


def magnifier(d, cx, cy, r, lw):
    # lens ring + handle
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=TEAL + (255,), width=lw)
    a = math.radians(45)
    x0, y0 = cx + (r + lw * 0.2) * math.cos(a), cy + (r + lw * 0.2) * math.sin(a)
    x1, y1 = cx + r * 1.95 * math.cos(a), cy + r * 1.95 * math.sin(a)
    d.line([x0, y0, x1, y1], fill=TEAL + (255,), width=int(lw * 1.5))
    d.ellipse([x1 - lw * 0.75, y1 - lw * 0.75, x1 + lw * 0.75, y1 + lw * 0.75], fill=TEAL + (255,))


def interrobang(d, cx, cy, size):
    f = font("InterDisplay-Black.otf", size)
    d.text((cx, cy), "?!", font=f, fill=AMBER + (255,), anchor="mm")


def sparkles(d, w, h, n, seed, scale=1.0, avoid=None):
    rnd = random.Random(seed)
    for _ in range(n):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        if avoid and avoid[0] < x < avoid[2] and avoid[1] < y < avoid[3]:
            continue
        r = rnd.uniform(1.5, 4.5) * scale
        a = rnd.randint(60, 200)
        col = rnd.choice([WHITE, TEAL, AMBER])
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (a,))


# ---------------------------------------------------------------- profile 800x800
def profile():
    W = 800 * S
    base = bg(800, 800).resize((W, W), Image.LANCZOS).convert("RGBA")
    deco = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    sparkles(ImageDraw.Draw(deco), W, W, 40, 3, S)
    base = Image.alpha_composite(base, deco)
    lay = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy, r = W * 0.45, W * 0.44, W * 0.26
    magnifier(d, cx, cy, r, int(W * 0.045))
    interrobang(d, cx + W * 0.005, cy - W * 0.01, int(W * 0.25))
    base = Image.alpha_composite(base, glow(lay, 18 * S))
    img = base.resize((800, 800), Image.LANCZOS).convert("RGB")
    img.save(os.path.join(OUT, "profile.png"))
    # circular preview (how YouTube shows it)
    m = Image.new("L", (800, 800), 0)
    ImageDraw.Draw(m).ellipse([0, 0, 799, 799], fill=255)
    prev = Image.new("RGB", (800, 800), (255, 255, 255))
    prev.paste(img, (0, 0), m)
    prev.save(os.path.join(OUT, "profile_preview_circle.png"))


# ---------------------------------------------------------------- banner 2560x1440 (safe 1546x423 centered)
def banner():
    W, H = 2560, 1440
    base = bg(W // 2, H // 2).resize((W, H), Image.LANCZOS).convert("RGBA")
    safe = ((W - 1546) // 2, (H - 423) // 2, (W + 1546) // 2, (H + 423) // 2)
    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(deco)
    sparkles(d, W, H, 260, 7, 1.4, avoid=safe)
    # orbiting planet (left), wave lines, cube (right) - outside text block
    px, py = safe[0] - 230, H // 2
    d.ellipse([px - 120, py - 120, px + 120, py + 120], fill=(36, 60, 120, 255), outline=TEAL + (255,), width=6)
    d.arc([px - 230, py - 60, px + 230, py + 60], 160, 380, fill=AMBER + (255,), width=8)
    cx, cy = safe[2] + 230, H // 2
    s = 95
    top = [(cx, cy - s), (cx + s, cy - s / 2), (cx, cy), (cx - s, cy - s / 2)]
    left = [(cx - s, cy - s / 2), (cx, cy), (cx, cy + s), (cx - s, cy + s / 2)]
    right = [(cx, cy), (cx + s, cy - s / 2), (cx + s, cy + s / 2), (cx, cy + s)]
    d.polygon(top, fill=AMBER + (255,)); d.polygon(left, fill=(196, 120, 20, 255)); d.polygon(right, fill=(150, 90, 15, 255))
    base = Image.alpha_composite(base, glow(deco, 10))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    words = NAME.upper().split()
    big = font("InterDisplay-Black.otf", 190)
    if len(words) >= 2:
        first, rest = words[0], " ".join(words[1:])
        w1 = d.textlength(first + " ", font=big); w2 = d.textlength(rest, font=big)
        x0 = W / 2 - (w1 + w2) / 2
        d.text((x0, H / 2 - 45), first, font=big, fill=WHITE + (255,), anchor="lm")
        d.text((x0 + w1, H / 2 - 45), rest, font=big, fill=AMBER + (255,), anchor="lm")
    else:
        d.text((W / 2, H / 2 - 45), NAME.upper(), font=big, fill=WHITE + (255,), anchor="mm")
    tag = font("Inter-Bold.otf", 58)
    d.text((W / 2, H / 2 + 120), "WEIRD FACTS  •  REAL SOURCES  •  EVERY DAY", font=tag, fill=TEAL + (255,), anchor="mm")
    base = Image.alpha_composite(base, glow(lay, 14))
    base.convert("RGB").save(os.path.join(OUT, "banner.png"))
    # preview with safe-area guide
    p = base.convert("RGB").copy(); ImageDraw.Draw(p).rectangle(safe, outline=(255, 0, 0), width=4)
    p.resize((1280, 720)).save(os.path.join(OUT, "banner_safe_guide.png"))


profile(); banner(); print("ok")
