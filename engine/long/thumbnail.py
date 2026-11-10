#!/usr/bin/env python3
"""Thumbnail (1280x720) in the channel style.

usage: python3 engine/thumbnail.py <metadata.md> <out.png> [--text "CRUTCH OR COACH?"]
Reads the thumbnail text from a line like:  - **Text (3 words):** "CRUTCH OR COACH?"
Art: split chat bubble (amber 'crutch' half / teal 'coach' half) + mini practice-vs-exam bars.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import skia  # noqa: E402
from gfx import rgb, paint, font, measure, rrect, circle, glow, draw_icon, AMBER, TEAL, WHITE, NAVY, RED  # noqa: E402

TW, TH = 1280, 720


def thumb_text(md_path):
    if md_path and os.path.exists(md_path):
        md = open(md_path, encoding='utf-8').read()
        m = re.search(r'thumbnail.*?text[^:\n]*:\**\s*["“]([^"”]+)["”]', md, re.I | re.S)
        if m:
            return m.group(1).strip()
    return 'THE EVIDENCE'


def draw(text_s, out):
    surf = skia.Surface(TW, TH)
    c = surf.getCanvas()
    c.clear(rgb('#081022'))
    for (x, y, r, col, a) in [(300, 200, 700, '#1B3466', .9), (1050, 560, 600, '#123F4E', .8), (900, 120, 380, '#3A2A1A', .6)]:
        sh = skia.GradientShader.MakeRadial((x, y), r, [rgb(col, a), rgb(col, 0)])
        c.drawPaint(skia.Paint(Shader=sh))
    # grain
    rng = np.random.default_rng(1)
    v = np.clip(128 + rng.normal(0, 60, (TH, TW)), 0, 255).astype(np.uint8)
    g = skia.Image.fromarray(np.dstack([v, v, v, np.full_like(v, 255)]))
    gp = skia.Paint(Alpha=10); gp.setBlendMode(skia.BlendMode.kOverlay)
    c.drawImage(g, 0, 0, skia.SamplingOptions(), gp)

    # ---- split chat bubble (right)
    bx, by, bw, bh = 770, 100, 450, 350
    bubble = skia.Path()
    bubble.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(bx, by, bw, bh), 90, 90))
    tail = skia.Path(); tail.moveTo(bx + 120, by + bh - 10); tail.lineTo(bx + 70, by + bh + 110); tail.lineTo(bx + 240, by + bh - 10); tail.close()
    bubble = skia.Op(bubble, tail, skia.PathOp.kUnion_PathOp)
    glow(c, bx + bw / 2, by + bh / 2, 420, AMBER, .22)
    c.save(); c.clipRect(skia.Rect.MakeLTRB(0, 0, bx + bw / 2, TH))
    c.drawPath(bubble, paint(AMBER))
    c.restore()
    c.save(); c.clipRect(skia.Rect.MakeLTRB(bx + bw / 2, 0, TW, TH))
    c.drawPath(bubble, paint(TEAL))
    c.restore()
    c.drawLine(bx + bw / 2, by - 10, bx + bw / 2, by + bh + 10, paint('#081022', 1, 10))
    # crutch (left half)
    cx, cy = bx + bw / 4, by + bh / 2
    p = paint(NAVY, 1, 18)
    c.drawLine(cx - 40, cy - 120, cx + 40, cy - 120, p)        # underarm pad
    c.drawLine(cx - 34, cy - 120, cx - 12, cy + 30, p)
    c.drawLine(cx + 34, cy - 120, cx + 12, cy + 30, p)
    c.drawLine(cx - 30, cy - 20, cx + 30, cy - 20, paint(NAVY, 1, 14))   # hand grip
    c.drawLine(cx, cy + 30, cx, cy + 140, p)
    c.drawLine(cx - 18, cy + 140, cx + 18, cy + 140, paint(NAVY, 1, 22))
    # lightbulb / coach (right half)
    draw_icon(c, 'lightbulb', bx + 3 * bw / 4, cy + 6, 230, 1.0, 0.4, '#081022', '#081022')

    # ---- mini practice vs exam bars (bottom right)
    ox, oy = 1010, 640
    rrect(c, ox - 30, oy - 150, 260, 190, 22, '#0B1730', .92)
    c.drawLine(ox - 10, oy - 40, ox + 210, oy - 40, paint('#8C9AB5', .8, 3))
    rrect(c, ox + 15, oy - 135, 60, 95, 8, '#3DDC84')
    rrect(c, ox + 120, oy - 40, 60, 60, 8, RED)
    ar = skia.Path(); ar.moveTo(ox + 45, oy - 128); ar.lineTo(ox + 30, oy - 108); ar.lineTo(ox + 60, oy - 108); ar.close()
    c.drawPath(ar, paint('#0B1730'))

    # ---- headline text (left)
    words = text_s.upper().split()
    if len(words) == 3:
        lines = [(words[0], AMBER), (words[1], WHITE), (words[2], TEAL)]
    else:
        half = (len(words) + 1) // 2
        lines = [(' '.join(words[:half]), WHITE), (' '.join(words[half:]), AMBER)]
    bases = [258, 388, 560] if len(lines) == 3 else [300, 480]
    for i, (ln, col) in enumerate(lines):
        small = len(lines) == 3 and i == 1
        size = 110 if small else 170
        y = bases[i]
        while measure(ln, size, 'display') > 650 and size > 60:
            size -= 6
        f = font(size, 'display')
        sh = paint('#000000', .55)
        c.drawString(ln, 64 + 6, y + 6, f, sh)
        c.drawString(ln, 64, y, f, paint(col))
    # brand tag
    rrect(c, 64, 40, 16, 16, 4, AMBER)
    f = font(22, 'bold')
    xx = 92
    for ch in 'ODDLY PROVEN':
        c.drawString(ch, xx, 56, f, paint('#C9D1E0', .9)); xx += f.measureText(ch) + 3
    img = surf.makeImageSnapshot()
    arr = np.frombuffer(img.tobytes(), np.uint8).reshape(TH, TW, 4)[:, :, [2, 1, 0]]
    from PIL import Image
    Image.fromarray(arr).save(out, optimize=True)
    print('thumbnail:', out, '| text:', text_s)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('metadata'); ap.add_argument('out'); ap.add_argument('--text')
    a = ap.parse_args()
    draw(a.text or thumb_text(a.metadata), a.out)
