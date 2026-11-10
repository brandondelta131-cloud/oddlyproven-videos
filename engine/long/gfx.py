"""Drawing primitives for the channel look (skia-python, antialiased).

Palette, fonts, easing, animated background, text helpers and a small
library of stylized vector icons. Everything draws at 1920x1080.
"""
import math
import os
import numpy as np
import skia

W, H = 1920, 1080
FPS = 30

# ---------------------------------------------------------------- palette
def rgb(hexs, a=1.0):
    hexs = hexs.lstrip('#')
    r, g, b = (int(hexs[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return skia.Color4f(r, g, b, max(0.0, min(1.0, a)))

NAVY = '#0A1326'
NAVY2 = '#111E38'
PANEL = '#15233F'
AMBER = '#F5A524'
TEAL = '#2EC4B6'
WHITE = '#F2F4F8'
MUTED = '#8C9AB5'
DIM = '#3A4A6B'
RED = '#E5604D'

# ---------------------------------------------------------------- fonts
FONT_DIR = '/usr/share/fonts/opentype/inter'
_FALLBACK = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
_WEIGHTS = {
    'light': 'Inter-Light.otf', 'regular': 'Inter-Regular.otf', 'medium': 'Inter-Medium.otf',
    'semibold': 'Inter-SemiBold.otf', 'bold': 'Inter-Bold.otf', 'extrabold': 'Inter-ExtraBold.otf',
    'black': 'Inter-Black.otf', 'display': 'InterDisplay-Black.otf',
    'displaybold': 'InterDisplay-Bold.otf', 'italic': 'Inter-Italic.otf',
    'serif': '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
    'serifreg': '/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed.ttf',
}
_tf_cache, _font_cache = {}, {}


def typeface(weight):
    if weight not in _tf_cache:
        p = _WEIGHTS.get(weight, _WEIGHTS['regular'])
        if not p.startswith('/'):
            p = os.path.join(FONT_DIR, p)
        if not os.path.exists(p):
            p = _FALLBACK
        _tf_cache[weight] = skia.Typeface.MakeFromFile(p)
    return _tf_cache[weight]


def font(size, weight='regular'):
    key = (round(size, 1), weight)
    if key not in _font_cache:
        f = skia.Font(typeface(weight), key[0])
        f.setSubpixel(True)
        f.setEdging(skia.Font.Edging.kAntiAlias)
        _font_cache[key] = f
    return _font_cache[key]


def measure(s, size, weight='regular', tracking=0.0):
    f = font(size, weight)
    return f.measureText(s) + tracking * max(0, len(s) - 1)


def paint(color, alpha=1.0, stroke=None, cap='round'):
    c = rgb(color, alpha) if isinstance(color, str) else color
    p = skia.Paint(AntiAlias=True, Color4f=c)
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(skia.Paint.kRound_Cap if cap == 'round' else skia.Paint.kButt_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


def text(c, s, x, y, size, weight='regular', color=WHITE, alpha=1.0, align='left', tracking=0.0):
    """Draw string with baseline at y. Returns drawn width."""
    if alpha <= 0.003 or not s:
        return 0
    f = font(size, weight)
    w = measure(s, size, weight, tracking)
    if align == 'center':
        x -= w / 2
    elif align == 'right':
        x -= w
    p = paint(color, alpha)
    if tracking:
        for ch in s:
            c.drawString(ch, x, y, f, p)
            x += f.measureText(ch) + tracking
    else:
        c.drawString(s, x, y, f, p)
    return w


def wrap(s, size, weight, maxw):
    words, lines, cur = s.split(), [], ''
    for wd in words:
        t = (cur + ' ' + wd).strip()
        if measure(t, size, weight) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def balance(s, size, weight, maxw, ls):
    """Re-wrap to the narrowest width that keeps the same line count (avoids orphans)."""
    if len(ls) < 2:
        return ls
    lo, hi = maxw * 0.4, maxw
    best = ls
    for _ in range(12):
        mid = (lo + hi) / 2
        t = wrap(s, size, weight, mid)
        if len(t) <= len(ls) and all(measure(l, size, weight) <= mid or ' ' not in l for l in t):
            best, hi = t, mid
        else:
            lo = mid
    return best


def fit_wrap(s, maxw, max_lines, size, weight, min_size=28):
    """Shrink font until wrapped text fits max_lines; balance line lengths."""
    while True:
        ls = wrap(s, size, weight, maxw)
        if len(ls) <= max_lines or size <= min_size:
            return balance(s, size, weight, maxw, ls), size
        size -= 4


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(t, start, dur):
    return clamp((t - start) / dur) if dur > 0 else float(t >= start)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x, k=1.7):
    x -= 1
    return 1 + (k + 1) * x ** 3 + k * x ** 2


def lerp(a, b, x):
    return a + (b - a) * x


# ---------------------------------------------------------------- shapes
def rrect(c, x, y, w, h, r, color, alpha=1.0, stroke=None):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r), paint(color, alpha, stroke))


def circle(c, x, y, r, color, alpha=1.0, stroke=None):
    c.drawCircle(x, y, r, paint(color, alpha, stroke))


def trim_path(path, frac):
    """Return the first `frac` of path length (draw-on effect)."""
    if frac >= 0.999:
        return path
    out = skia.Path()
    if frac <= 0.001:
        return out
    m = skia.PathMeasure(path, False)
    while True:
        L = m.getLength()
        m.getSegment(0, L * frac, out, True)
        if not m.nextContour():
            break
    return out


def draw_path(c, path, color, alpha=1.0, stroke=6, frac=1.0):
    if alpha <= 0.003 or frac <= 0.001:
        return
    c.drawPath(trim_path(path, frac), paint(color, alpha, stroke))


def line(c, x1, y1, x2, y2, color, alpha=1.0, stroke=4, frac=1.0):
    if frac <= 0.001:
        return
    c.drawLine(x1, y1, lerp(x1, x2, frac), lerp(y1, y2, frac), paint(color, alpha, stroke))


def arrow(c, x1, y1, x2, y2, color, alpha=1.0, stroke=6, frac=1.0, head=22):
    if frac <= 0.001:
        return
    xe, ye = lerp(x1, x2, frac), lerp(y1, y2, frac)
    c.drawLine(x1, y1, xe, ye, paint(color, alpha, stroke))
    if frac > 0.6:
        a = math.atan2(y2 - y1, x2 - x1)
        hp = skia.Path()
        hp.moveTo(xe - head * math.cos(a - .45), ye - head * math.sin(a - .45))
        hp.lineTo(xe, ye)
        hp.lineTo(xe - head * math.cos(a + .45), ye - head * math.sin(a + .45))
        c.drawPath(hp, paint(color, alpha * clamp((frac - .6) / .3), stroke))


def arc(c, cx, cy, r, start_deg, sweep_deg, color, alpha=1.0, stroke=10):
    if abs(sweep_deg) < 0.1:
        return
    p = skia.Path()
    p.addArc(skia.Rect.MakeLTRB(cx - r, cy - r, cx + r, cy + r), start_deg, sweep_deg)
    c.drawPath(p, paint(color, alpha, stroke))


def glow(c, x, y, r, color, alpha=0.35):
    sh = skia.GradientShader.MakeRadial((x, y), r, [rgb(color, alpha), rgb(color, 0)])
    c.drawCircle(x, y, r, skia.Paint(AntiAlias=True, Shader=sh))


# ---------------------------------------------------------------- background
class Background:
    """Slow drifting navy gradient blobs + film grain + faint dot grid.

    The gradient is rendered small and upscaled (cheap, and blur-smooth).
    Grain uses a handful of precomputed noise tiles, cycled per frame.
    """

    def __init__(self, seed=7):
        self.small = skia.Surface(320, 180)
        rng = np.random.default_rng(seed)
        self.grain = []
        for _ in range(4):
            n = rng.normal(0, 1, (H // 2, W // 2))
            v = np.clip(128 + n * 60, 0, 255).astype(np.uint8)
            a = np.full_like(v, 255)
            arr = np.dstack([v, v, v, a])
            self.grain.append(skia.Image.fromarray(arr))
        # static dot grid layer
        surf = skia.Surface(W, H)
        gc = surf.getCanvas()
        gc.clear(skia.Color4f(0, 0, 0, 0))
        p = paint(MUTED, 0.06)
        for gx in range(60, W, 60):
            for gy in range(60, H, 60):
                gc.drawCircle(gx, gy, 1.4, p)
        self.grid = surf.makeImageSnapshot()
        # vignette
        surf = skia.Surface(W, H)
        vc = surf.getCanvas()
        vc.clear(skia.Color4f(0, 0, 0, 0))
        sh = skia.GradientShader.MakeRadial((W / 2, H / 2), W * 0.72,
                                            [skia.Color4f(0, 0, 0, 0), skia.Color4f(0, 0, 0, 0), skia.Color4f(0, 0, .02, .55)],
                                            [0, .55, 1])
        vc.drawPaint(skia.Paint(Shader=sh))
        self.vignette = surf.makeImageSnapshot()

    def draw(self, c, gt, accent_shift=0.0):
        sc = self.small.getCanvas()
        sc.clear(rgb(NAVY))
        blobs = [
            (0.25 + 0.08 * math.sin(gt * 0.11), 0.30 + 0.10 * math.cos(gt * 0.09), 0.55, '#1B3466', 0.75),
            (0.78 + 0.07 * math.cos(gt * 0.08), 0.70 + 0.08 * math.sin(gt * 0.12), 0.50, '#123F4E', 0.55),
            (0.60 + 0.10 * math.sin(gt * 0.05 + 1), 0.15 + 0.06 * math.cos(gt * 0.07), 0.35, '#3A2A1A', 0.30 + 0.15 * accent_shift),
        ]
        for bx, by, br, col, a in blobs:
            x, y, r = bx * 320, by * 180, br * 320
            sh = skia.GradientShader.MakeRadial((x, y), r, [rgb(col, a), rgb(col, 0)])
            sc.drawPaint(skia.Paint(Shader=sh))
        img = self.small.makeImageSnapshot()
        c.drawImageRect(img, skia.Rect.MakeWH(W, H), skia.SamplingOptions(skia.FilterMode.kLinear))
        c.drawImage(self.grid, 0, 0)
        g = self.grain[int(gt * FPS) % len(self.grain)]
        gp = skia.Paint(Alpha=int(255 * 0.035))
        gp.setBlendMode(skia.BlendMode.kOverlay)
        c.drawImageRect(g, skia.Rect.MakeWH(W, H), skia.SamplingOptions(), gp)
        c.drawImage(self.vignette, 0, 0)


# ---------------------------------------------------------------- icons
# All icons draw in a 200x200 box centered on (0,0) after translate/scale.
# `p` is the draw-on progress 0..1, `t` is time for idle motion.

def _P():
    return skia.Path()


def icon_brain(c, p, t, col, col2):
    L = _P()
    L.moveTo(0, -78); L.cubicTo(-30, -96, -70, -84, -74, -52); L.cubicTo(-100, -44, -102, -6, -84, 8)
    L.cubicTo(-100, 30, -86, 66, -56, 66); L.cubicTo(-46, 88, -12, 92, 0, 74)
    R = _P()
    R.moveTo(0, -78); R.cubicTo(30, -96, 70, -84, 74, -52); R.cubicTo(100, -44, 102, -6, 84, 8)
    R.cubicTo(100, 30, 86, 66, 56, 66); R.cubicTo(46, 88, 12, 92, 0, 74)
    mid = _P(); mid.moveTo(0, -78); mid.lineTo(0, 74)
    folds = _P()
    folds.moveTo(-60, -40); folds.cubicTo(-40, -50, -24, -36, -30, -18)
    folds.moveTo(-70, 10); folds.cubicTo(-50, 0, -30, 16, -40, 34)
    folds.moveTo(-28, 48); folds.cubicTo(-16, 36, -8, 50, -10, 60)
    folds.moveTo(60, -40); folds.cubicTo(40, -50, 24, -36, 30, -18)
    folds.moveTo(70, 10); folds.cubicTo(50, 0, 30, 16, 40, 34)
    folds.moveTo(28, 48); folds.cubicTo(16, 36, 8, 50, 10, 60)
    draw_path(c, L, col, 1, 7, ease_out(p)); draw_path(c, R, col, 1, 7, ease_out(p))
    draw_path(c, mid, col, .6, 4, ease_out(prog(p, .3, .7)))
    draw_path(c, folds, col2, .9, 5, ease_out(prog(p, .45, .55)))
    # synapse sparks
    for i, (x, y) in enumerate([(-44, -58), (50, -20), (-58, 30), (36, 44), (-20, 0)]):
        a = (0.5 + 0.5 * math.sin(t * 3 + i * 1.7)) * prog(p, .7, .3)
        circle(c, x, y, 5, col2, a)


def icon_robot(c, p, t, col, col2):
    e = ease_back(prog(p, 0, .7))
    c.save(); c.scale(max(e, .001), max(e, .001))
    rrect(c, -70, -50, 140, 110, 26, PANEL, 1)
    rrect(c, -70, -50, 140, 110, 26, col, 1, 6)
    line(c, 0, -50, 0, -80, col, 1, 6)
    circle(c, 0, -86, 9, col2, 1)
    blink = 0.15 if (t % 3.4) < 0.12 else 1
    rrect(c, -44, -18, 26, 26 * blink, 8, col2, 1)
    rrect(c, 18, -18, 26, 26 * blink, 8, col2, 1)
    rrect(c, -30, 26, 60, 10, 5, col, .8)
    rrect(c, -84, -10, 14, 36, 6, col, 1)
    rrect(c, 70, -10, 14, 36, 6, col, 1)
    c.restore()


def icon_chat(c, p, t, col, col2):
    a = ease_back(prog(p, 0, .5)); b = ease_back(prog(p, .3, .5))
    for k, (ox, oy, s, cl) in enumerate([(-24, -26, a, col), (30, 34, b, col2)]):
        if s <= 0.01:
            continue
        c.save(); c.translate(ox, oy); c.scale(s, s)
        rrect(c, -70, -38, 140, 76, 30, cl, .18)
        rrect(c, -70, -38, 140, 76, 30, cl, 1, 6)
        tail = _P()
        if k == 0:
            tail.moveTo(-40, 36); tail.lineTo(-56, 62); tail.lineTo(-16, 38)
        else:
            tail.moveTo(40, 36); tail.lineTo(56, 62); tail.lineTo(16, 38)
        c.drawPath(tail, paint(cl, 1, 6))
        if k == 1:
            for i in range(3):
                bounce = 4 * math.sin(t * 6 - i * .8)
                circle(c, -28 + i * 28, bounce, 7, cl, 1)
        else:
            line(c, -42, -8, 42, -8, cl, .9, 6); line(c, -42, 12, 14, 12, cl, .9, 6)
        c.restore()


def icon_student(c, p, t, col, col2):
    e = ease_out(prog(p, 0, .6))
    c.save(); c.translate(0, 20 * (1 - e))
    circle(c, 0, -40, 30, col, e)
    body = _P(); body.moveTo(-56, 76); body.cubicTo(-56, 10, 56, 10, 56, 76); body.close()
    c.drawPath(body, paint(col, e))
    cap = _P(); cap.moveTo(-50, -72); cap.lineTo(0, -92); cap.lineTo(50, -72); cap.lineTo(0, -52); cap.close()
    c.drawPath(cap, paint(col2, prog(p, .4, .4)))
    line(c, 40, -68, 40, -42, col2, prog(p, .5, .3), 4)
    c.restore()


def icon_document(c, p, t, col, col2):
    e = ease_out(prog(p, 0, .5))
    c.save(); c.translate(0, 30 * (1 - e))
    rrect(c, -62, -80, 124, 160, 14, PANEL, e)
    rrect(c, -62, -80, 124, 160, 14, col, e, 6)
    for i in range(5):
        w = [84, 70, 84, 56, 76][i]
        line(c, -42, -46 + i * 26, -42 + w, -46 + i * 26, col2 if i == 0 else col, .9, 6, ease_out(prog(p, .3 + i * .1, .3)))
    c.restore()


def icon_magnifier(c, p, t, col, col2):
    dx = 8 * math.sin(t * 1.3); dy = 6 * math.cos(t * 1.1)
    c.save(); c.translate(dx, dy)
    ring = _P(); ring.addCircle(-14, -14, 52)
    draw_path(c, ring, col, 1, 10, ease_out(p))
    circle(c, -14, -14, 46, col, .12 * p)
    line(c, 24, 24, 70, 70, col2, 1, 16, ease_out(prog(p, .5, .4)))
    c.restore()


def icon_flask(c, p, t, col, col2):
    fl = _P()
    fl.moveTo(-22, -80); fl.lineTo(-22, -20); fl.lineTo(-68, 64); fl.cubicTo(-74, 76, -66, 84, -54, 84)
    fl.lineTo(54, 84); fl.cubicTo(66, 84, 74, 76, 68, 64); fl.lineTo(22, -20); fl.lineTo(22, -80)
    lv = 0.5 + 0.04 * math.sin(t * 2)
    liq = _P(); liq.moveTo(-48, 28); liq.lineTo(48, 28); liq.lineTo(68, 64); liq.cubicTo(74, 76, 66, 84, 54, 84)
    liq.lineTo(-54, 84); liq.cubicTo(-66, 84, -74, 76, -68, 64); liq.close()
    c.drawPath(liq, paint(col2, .55 * prog(p, .5, .4)))
    draw_path(c, fl, col, 1, 7, ease_out(p))
    line(c, -34, -80, 34, -80, col, 1, 7, ease_out(prog(p, .6, .3)))
    for i in range(3):
        ph = (t * .6 + i / 3) % 1
        circle(c, -14 + i * 14, 70 - ph * 80, 5 + 3 * i % 2, col2, (1 - ph) * prog(p, .6, .3))
    _ = lv


def icon_clock(c, p, t, col, col2):
    ring = _P(); ring.addCircle(0, 0, 76)
    draw_path(c, ring, col, 1, 8, ease_out(p))
    a = t * 1.5
    line(c, 0, 0, 50 * math.sin(a), -50 * math.cos(a), col2, prog(p, .5, .4), 7)
    line(c, 0, 0, 30 * math.sin(a / 12), -30 * math.cos(a / 12), col, prog(p, .5, .4), 8)
    circle(c, 0, 0, 8, col2, prog(p, .5, .4))


def icon_check(c, p, t, col, col2):
    ring = _P(); ring.addCircle(0, 0, 76)
    draw_path(c, ring, col, 1, 8, ease_out(prog(p, 0, .6)))
    ck = _P(); ck.moveTo(-34, 2); ck.lineTo(-8, 28); ck.lineTo(38, -24)
    draw_path(c, ck, col2, 1, 12, ease_out(prog(p, .45, .5)))


def icon_warning(c, p, t, col, col2):
    tri = _P(); tri.moveTo(0, -80); tri.lineTo(84, 70); tri.lineTo(-84, 70); tri.close()
    c.drawPath(trim_path(tri, ease_out(p)), paint(col, 1, 8))
    pulse = .7 + .3 * math.sin(t * 4)
    line(c, 0, -26, 0, 22, col2, prog(p, .6, .3) * pulse, 12)
    circle(c, 0, 46, 7, col2, prog(p, .6, .3) * pulse)


def icon_question(c, p, t, col, col2):
    ring = _P(); ring.addCircle(0, 0, 80)
    draw_path(c, ring, col, 1, 7, ease_out(p))
    q = _P(); q.moveTo(-28, -26); q.cubicTo(-28, -64, 30, -64, 30, -28); q.cubicTo(30, -4, 0, -2, 0, 22)
    draw_path(c, q, col2, 1, 12, ease_out(prog(p, .3, .6)))
    circle(c, 0, 50, 8, col2, prog(p, .8, .2))


def icon_chart(c, p, t, col, col2):
    line(c, -80, 70, 80, 70, col, 1, 6, ease_out(p))
    line(c, -80, 70, -80, -80, col, 1, 6, ease_out(p))
    for i, h in enumerate([50, 90, 70, 120]):
        e = ease_back(prog(p, .3 + i * .1, .35))
        rrect(c, -62 + i * 36, 62 - h * e, 24, h * e, 5, col2 if i == 3 else col, .9)


def icon_lightbulb(c, p, t, col, col2):
    b = _P(); b.moveTo(-26, 40); b.cubicTo(-26, 10, -60, 0, -60, -32); b.cubicTo(-60, -70, -30, -88, 0, -88)
    b.cubicTo(30, -88, 60, -70, 60, -32); b.cubicTo(60, 0, 26, 10, 26, 40); b.close()
    glow(c, 0, -32, 110, col2, .25 * prog(p, .6, .4) * (.8 + .2 * math.sin(t * 3)))
    draw_path(c, b, col, 1, 7, ease_out(p))
    line(c, -22, 58, 22, 58, col, 1, 7, prog(p, .5, .3)); line(c, -16, 76, 16, 76, col, 1, 7, prog(p, .6, .3))
    fil = _P(); fil.moveTo(-14, 30); fil.lineTo(-14, -20); fil.lineTo(0, -6); fil.lineTo(14, -20); fil.lineTo(14, 30)
    draw_path(c, fil, col2, 1, 5, ease_out(prog(p, .5, .4)))


def icon_scale(c, p, t, col, col2):
    tilt = 10 * math.sin(t * 1.2) * prog(p, .6, .4)
    line(c, 0, -70, 0, 80, col, 1, 7, ease_out(p)); line(c, -40, 80, 40, 80, col, 1, 7, ease_out(p))
    c.save(); c.translate(0, -60); c.rotate(tilt)
    line(c, -80, 0, 80, 0, col, 1, 7, ease_out(prog(p, .3, .4)))
    for sx, cl in ((-80, col2), (80, TEAL)):
        line(c, sx, 0, sx - 26, 60, cl, prog(p, .5, .3), 4); line(c, sx, 0, sx + 26, 60, cl, prog(p, .5, .3), 4)
        pan = _P(); pan.moveTo(sx - 34, 60); pan.cubicTo(sx - 30, 84, sx + 30, 84, sx + 34, 60); pan.close()
        c.drawPath(pan, paint(cl, prog(p, .5, .3)))
    c.restore()


def icon_wave(c, p, t, col, col2):
    """EEG / brain-activity trace."""
    rrect(c, -90, -70, 180, 140, 18, PANEL, prog(p, 0, .3))
    rrect(c, -90, -70, 180, 140, 18, col, prog(p, 0, .3), 5)
    w = _P()
    for i in range(61):
        x = -76 + i * 152 / 60
        y = 22 * math.sin(i * .55 + t * 4) * math.sin(i * .13) + 10 * math.sin(i * 1.7 + t * 7)
        (w.moveTo if i == 0 else w.lineTo)(x, y)
    draw_path(c, w, col2, 1, 5, ease_out(prog(p, .2, .7)))


def icon_phone(c, p, t, col, col2):
    e = ease_back(prog(p, 0, .6))
    c.save(); c.scale(max(e, .001), max(e, .001))
    rrect(c, -50, -88, 100, 176, 18, PANEL, 1); rrect(c, -50, -88, 100, 176, 18, col, 1, 6)
    rrect(c, -16, -78, 32, 6, 3, col, .8)
    for i in range(3):
        rrect(c, -34, -50 + i * 38, 68, 26, 8, col2 if i == 1 else col, .5)
    c.restore()


def icon_book(c, p, t, col, col2):
    L = _P(); L.moveTo(0, -60); L.cubicTo(-30, -76, -70, -76, -90, -64); L.lineTo(-90, 70); L.cubicTo(-70, 58, -30, 58, 0, 74); L.close()
    R = _P(); R.moveTo(0, -60); R.cubicTo(30, -76, 70, -76, 90, -64); R.lineTo(90, 70); R.cubicTo(70, 58, 30, 58, 0, 74); R.close()
    draw_path(c, L, col, 1, 7, ease_out(p)); draw_path(c, R, col, 1, 7, ease_out(p))
    for i in range(3):
        line(c, -70, -36 + i * 28, -20, -40 + i * 28, col2, .8, 5, prog(p, .5 + i * .1, .3))
        line(c, 20, -40 + i * 28, 70, -36 + i * 28, col2, .8, 5, prog(p, .55 + i * .1, .3))


def icon_people(c, p, t, col, col2):
    for i, (x, s, cl) in enumerate([(-60, .75, col), (60, .75, col), (0, 1.0, col2)]):
        e = ease_back(prog(p, i * .15, .5))
        if e <= 0.01:
            continue
        c.save(); c.translate(x, 10 if s < 1 else 0); c.scale(s * e, s * e)
        circle(c, 0, -40, 28, cl, 1)
        b = _P(); b.moveTo(-50, 70); b.cubicTo(-50, 6, 50, 6, 50, 70); b.close()
        c.drawPath(b, paint(cl, 1))
        c.restore()


def icon_pencil(c, p, t, col, col2):
    e = ease_out(p)
    c.save(); c.rotate(-40)
    rrect(c, -18, -80, 36, 120, 6, col, e)
    tip = _P(); tip.moveTo(-18, 40); tip.lineTo(0, 76); tip.lineTo(18, 40); tip.close()
    c.drawPath(tip, paint(col2, e))
    rrect(c, -18, -96, 36, 18, 6, MUTED, e)
    c.restore()
    sq = _P(); sq.moveTo(-70, 84)
    for i in range(8):
        sq.cubicTo(-62 + i * 16, 70, -58 + i * 16, 98, -50 + i * 16, 84)
    draw_path(c, sq, col2, .8, 4, ease_out(prog(p, .4, .6)))


def icon_building(c, p, t, col, col2):
    e = ease_out(p)
    roof = _P(); roof.moveTo(-84, -30); roof.lineTo(0, -80); roof.lineTo(84, -30); roof.close()
    c.drawPath(trim_path(roof, e), paint(col2, 1, 7))
    for i in range(4):
        h = 90 * ease_out(prog(p, .2 + i * .1, .4))
        rrect(c, -62 + i * 36, 60 - h, 16, h, 4, col, 1)
    line(c, -90, 70, 90, 70, col, 1, 8, e)


def icon_calendar(c, p, t, col, col2):
    e = ease_back(prog(p, 0, .6))
    c.save(); c.scale(max(e, .001), max(e, .001))
    rrect(c, -76, -64, 152, 144, 16, PANEL, 1); rrect(c, -76, -64, 152, 144, 16, col, 1, 6)
    rrect(c, -76, -64, 152, 40, 16, col2, 1)
    for i in range(3):
        for j in range(4):
            rrect(c, -56 + j * 30, -6 + i * 26, 18, 14, 4, col, .6 if (i * 4 + j) != 6 else 1)
    line(c, -40, -78, -40, -54, col, 1, 7); line(c, 40, -78, 40, -54, col, 1, 7)
    c.restore()


ICONS = {
    'brain': icon_brain, 'robot': icon_robot, 'chat': icon_chat, 'student': icon_student,
    'document': icon_document, 'magnifier': icon_magnifier, 'flask': icon_flask, 'clock': icon_clock,
    'check': icon_check, 'warning': icon_warning, 'question': icon_question, 'chart': icon_chart,
    'lightbulb': icon_lightbulb, 'scale': icon_scale, 'wave': icon_wave, 'phone': icon_phone,
    'book': icon_book, 'people': icon_people, 'pencil': icon_pencil,
    'building': icon_building, 'calendar': icon_calendar,
}
GRAY = '#7D8BA6'


def draw_icon(c, name, cx, cy, size, p, t, col=WHITE, col2=AMBER, alpha=1.0):
    if alpha <= 0.003 or p <= 0.001:
        return
    fn = ICONS.get(name, icon_question)
    s = size / 200.0
    if alpha < 0.999:
        c.saveLayerAlpha(None, int(255 * alpha))
    else:
        c.save()
    c.translate(cx, cy)
    c.scale(s, s)
    fn(c, clamp(p), t, col, col2)
    c.restore()


ICON_KEYWORDS = [
    ('wave', ['eeg', 'brain activity', 'brainwave', 'neural activity', 'connectivity', 'scan', 'electrode']),
    ('robot', ['robot', 'chatbot', 'llm', 'chatgpt', 'gpt', ' ai ', 'ai ', 'artificial', 'assistant', 'model']),
    ('chat', ['chat', 'conversation', 'prompt', 'message', 'bubble', 'ask']),
    ('brain', ['brain', 'memory', 'think', 'cognit', 'mind', 'neuro', 'remember', 'recall']),
    ('student', ['student', 'learner', 'pupil', 'school', 'class', 'university', 'graduate']),
    ('people', ['people', 'participants', 'volunteers', 'workers', 'adults', 'group', 'sample', 'survey']),
    ('pencil', ['write', 'writing', 'essay', 'draft', 'pencil']),
    ('document', ['paper', 'study', 'report', 'article', 'preprint', 'document', 'journal']),
    ('magnifier', ['search', 'google', 'look', 'investig', 'evidence', 'examine', 'detail', 'fine print', 'closer']),
    ('flask', ['experiment', 'lab', 'trial', 'random', 'test']),
    ('warning', ['warning', 'caveat', 'limit', 'caution', 'risk', 'danger', 'small sample', 'not peer']),
    ('question', ['question', 'unknown', 'unclear', 'why', 'what', 'doubt', 'myth', 'claim']),
    ('check', ['takeaway', 'tip', 'conclusion', 'verdict', 'do this', 'check', 'rule']),
    ('lightbulb', ['idea', 'insight', 'learn', 'understand', 'creativ']),
    ('clock', ['time', 'minute', 'hour', 'week', 'month', 'later', 'session', 'long-term', 'delay']),
    ('scale', ['balance', 'trade-off', 'tradeoff', 'weigh', 'both']),
    ('phone', ['phone', 'app', 'screen', 'social media', 'notification']),
    ('book', ['book', 'read', 'homework', 'textbook', 'library']),
    ('chart', ['data', 'chart', 'graph', 'score', 'result', 'percent', 'performance', 'grade']),
]


def pick_icon(textv, avoid=()):
    t = ' ' + textv.lower() + ' '
    best = None
    for name, kws in ICON_KEYWORDS:
        if name in avoid:
            continue
        for k in kws:
            if k in t:
                pos = t.index(k)
                if best is None or pos < best[1]:
                    best = (name, pos)
                break
    return best[0] if best else next(n for n in ('question', 'chart', 'lightbulb', 'document', 'check') if n not in avoid)
