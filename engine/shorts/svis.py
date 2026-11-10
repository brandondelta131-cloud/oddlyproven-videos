"""Animated vector visuals for vertical Shorts (skia).

Every visual draws centred on (0,0) inside a ~600x600 box after the caller
translates/scales. Signature: fn(c, t, p, A, B, seed)
  t    seconds since the segment started (keeps moving every frame)
  p    0..1 draw-on/entrance progress
  A, B accent colours (yellow, cyan hex)
"""
import math
import re
import skia
import vgfx as g
from vgfx import paint, rgb, circle, rrect, line, arc, glow, draw_path, clamp, ease_out, lerp, text

WHITE = '#FFFFFF'
DARK = '#0B0F1E'


def P():
    return skia.Path()


def _rng(seed, i):
    x = math.sin(seed * 12.9898 + i * 78.233) * 43758.5453
    return x - math.floor(x)


def fillp(c, path, col, a=1.0):
    c.drawPath(path, paint(col, a))


def sparkles(c, t, seed, n=10, R=290, col=WHITE):
    for i in range(n):
        ang = _rng(seed, i) * 6.283 + t * 0.25 * (1 if i % 2 else -1)
        r = R * (0.75 + 0.3 * _rng(seed, i + 50))
        x, y = r * math.cos(ang), r * math.sin(ang)
        tw = 0.5 + 0.5 * math.sin(t * 5 + i * 1.7)
        s = 5 + 9 * tw
        pth = P()
        pth.moveTo(x, y - s * 2); pth.lineTo(x + s * .5, y - s * .5); pth.lineTo(x + s * 2, y); pth.lineTo(x + s * .5, y + s * .5)
        pth.lineTo(x, y + s * 2); pth.lineTo(x - s * .5, y + s * .5); pth.lineTo(x - s * 2, y); pth.lineTo(x - s * .5, y - s * .5); pth.close()
        fillp(c, pth, col, 0.35 + 0.6 * tw)


# ---------------------------------------------------------------- space
def v_planet(c, t, p, A, B, seed):
    sparkles(c, t, seed, 12, 300)
    R = 170 * ease_out(p)
    c.save(); c.rotate(-18 + 4 * math.sin(t * .8))
    # back ring
    ring = skia.Rect.MakeLTRB(-300, -70, 300, 70)
    rp = paint(B, .9, 18); c.drawArc(ring, 180, 180, False, rp)
    sh = skia.GradientShader.MakeLinear([(-R, -R), (R, R)], [rgb('#FF8A3D'), rgb('#B8337A'), rgb('#3A1C71')])
    c.drawCircle(0, 0, R, skia.Paint(AntiAlias=True, Shader=sh))
    for k in range(3):  # bands
        yy = -R * .5 + k * R * .45 + 8 * math.sin(t * 1.5 + k)
        c.save(); c.clipPath(_circ(0, 0, R), doAntiAlias=True)
        rrect(c, -R, yy, 2 * R, R * .16, R * .08, '#FFFFFF', .12)
        c.restore()
    c.drawArc(ring, 0, 180, False, paint(A, .95, 18))
    c.restore()
    a = t * 1.6
    mx, my = 270 * math.cos(a), 110 * math.sin(a)
    circle(c, mx, my, 30, '#DDE3F0'); circle(c, mx - 8, my - 6, 7, '#9AA3B8')


def _circ(x, y, r):
    p = P(); p.addCircle(x, y, r); return p


def v_stars(c, t, p, A, B, seed):
    # warp-speed starfield: streaks flying out from centre
    for i in range(70):
        ang = _rng(seed, i) * 6.283
        sp = 0.35 + _rng(seed, i + 99)
        d = ((t * sp * 0.6 + _rng(seed, i + 7)) % 1.0)
        r0 = 20 + 380 * d * d
        r1 = r0 + 10 + 60 * d
        col = A if i % 9 == 0 else (B if i % 5 == 0 else WHITE)
        line(c, r0 * math.cos(ang), r0 * math.sin(ang), r1 * math.cos(ang), r1 * math.sin(ang), col, min(1, d * 2.5), 3 + 4 * d)
    glow(c, 0, 0, 160, B, .45)
    circle(c, 0, 0, 26 + 6 * math.sin(t * 6), WHITE, .95)


def v_sun(c, t, p, A, B, seed):
    glow(c, 0, 0, 330, A, .45)
    c.save(); c.rotate(t * 25)
    for i in range(12):
        c.save(); c.rotate(i * 30)
        L = 70 + 25 * math.sin(t * 4 + i)
        rrect(c, -12, -170 - L, 24, L, 12, A, .95 * p)
        c.restore()
    c.restore()
    sh = skia.GradientShader.MakeRadial((-30, -30), 170, [rgb('#FFF6B0'), rgb('#FFC400'), rgb('#FF7A00')])
    c.drawCircle(0, 0, 140 * ease_out(p), skia.Paint(AntiAlias=True, Shader=sh))


def v_atom(c, t, p, A, B, seed):
    glow(c, 0, 0, 200, B, .35)
    for k in range(3):
        c.save(); c.rotate(k * 60 + t * 12)
        rect = skia.Rect.MakeLTRB(-270, -90, 270, 90)
        c.drawOval(rect, paint(B if k != 1 else A, .9, 9))
        a = t * (2.2 + k * .4) + k
        circle(c, 270 * math.cos(a), 90 * math.sin(a), 22, WHITE)
        c.restore()
    for i, (dx, dy) in enumerate([(-22, -14), (20, -16), (0, 18), (-18, 22), (22, 16)]):
        circle(c, dx * p, dy * p, 30, A if i % 2 else '#FF5D73')


# ---------------------------------------------------------------- earth / water
def v_waves(c, t, p, A, B, seed):
    circle(c, 150, -170, 80, A, .95); glow(c, 150, -170, 180, A, .3)
    cols = ['#1B6CFF', B, '#0FA3D8', '#FFFFFF']
    for k in range(4):
        pth = P(); y0 = -40 + k * 70; amp = 34 - k * 4; ph = t * (2.2 + k * .5) * (1 if k % 2 else -1)
        pth.moveTo(-320, 330)
        for x in range(-320, 330, 16):
            pth.lineTo(x, y0 + amp * math.sin(x / 60 + ph))
        pth.lineTo(320, 330); pth.close()
        c.save(); c.clipRect(skia.Rect.MakeLTRB(-320, -330, 320, 300))
        fillp(c, pth, cols[k], .55 + .12 * k if k < 3 else .18)
        c.restore()


def v_drop(c, t, p, A, B, seed):
    for k in range(3):
        ph = (t * .7 + k / 3) % 1
        c.drawOval(skia.Rect.MakeLTRB(-260 * ph, 200 - 50 * ph, 260 * ph, 200 + 50 * ph), paint(B, (1 - ph) * .9, 6))
    y = -60 + 25 * math.sin(t * 3)
    pth = P(); pth.moveTo(0, y - 200); pth.cubicTo(60, y - 100, 130, y - 20, 130, y + 50)
    pth.cubicTo(130, y + 130, 65, y + 180, 0, y + 180); pth.cubicTo(-65, y + 180, -130, y + 130, -130, y + 50)
    pth.cubicTo(-130, y - 20, -60, y - 100, 0, y - 200); pth.close()
    sh = skia.GradientShader.MakeLinear([(0, y - 200), (0, y + 180)], [rgb('#8FF3FF'), rgb('#1B6CFF')])
    c.drawPath(pth, skia.Paint(AntiAlias=True, Shader=sh))
    c.drawOval(skia.Rect.MakeXYWH(-80, y + 10, 34, 70), paint(WHITE, .6))


def v_globe(c, t, p, A, B, seed):
    R = 220
    glow(c, 0, 0, 320, B, .35)
    sh = skia.GradientShader.MakeRadial((-70, -80), 300, [rgb('#3FA9FF'), rgb('#0B3D91')])
    c.drawCircle(0, 0, R, skia.Paint(AntiAlias=True, Shader=sh))
    c.save(); c.clipPath(_circ(0, 0, R), doAntiAlias=True)
    # continents: blobs sliding horizontally (rotation)
    for i in range(5):
        x = ((_rng(seed, i) * 2 * R + t * 60) % (3 * R)) - 1.5 * R
        y = (_rng(seed, i + 9) - .5) * 1.4 * R
        sx = math.sqrt(max(0.05, 1 - (x / R) ** 2))
        c.drawOval(skia.Rect.MakeXYWH(x - 70 * sx, y - 45, 140 * sx, 90 + 30 * _rng(seed, i + 3)), paint('#38D27A', .95))
    for k in range(-2, 3):
        c.drawOval(skia.Rect.MakeLTRB(-R, k * 80 - 8, R, k * 80 + 8), paint(WHITE, .15, 3))
    off = (t * 0.35) % 1
    for k in range(6):
        ph = ((k / 6 + off) % 1) * math.pi
        w = R * math.cos(ph)
        c.drawOval(skia.Rect.MakeLTRB(-abs(w), -R, abs(w), R), paint(WHITE, .18, 3))
    c.restore()
    c.drawCircle(0, 0, R, paint(WHITE, .5, 5))
    # bouncing pin
    by = -R - 30 - 30 * abs(math.sin(t * 3.5))
    _pin(c, 60, by, A)


def _pin(c, x, y, col):
    pth = P(); pth.moveTo(x, y + 70); pth.cubicTo(x - 20, y + 40, x - 45, y + 15, x - 45, y - 10)
    pth.cubicTo(x - 45, y - 40, x - 25, y - 55, x, y - 55); pth.cubicTo(x + 25, y - 55, x + 45, y - 40, x + 45, y - 10)
    pth.cubicTo(x + 45, y + 15, x + 20, y + 40, x, y + 70); pth.close()
    fillp(c, pth, col); circle(c, x, y - 10, 16, DARK)


def v_map(c, t, p, A, B, seed):
    c.save(); c.rotate(-6 + 2 * math.sin(t))
    xs = [-270, -90, 90, 270]
    for i in range(3):
        pth = P(); sk = 20 if i % 2 else -20
        pth.moveTo(xs[i], -200 + sk); pth.lineTo(xs[i + 1], -200 - sk); pth.lineTo(xs[i + 1], 200 - sk); pth.lineTo(xs[i], 200 + sk); pth.close()
        fillp(c, pth, ['#F4E3B5', '#E8D29A', '#F4E3B5'][i])
    c.drawOval(skia.Rect.MakeXYWH(-230, -120, 160, 110), paint('#7FC97F', .9))
    c.drawOval(skia.Rect.MakeXYWH(40, 20, 190, 120), paint('#7FC97F', .9))
    route = P(); route.moveTo(-200, 140); route.cubicTo(-120, -40, 40, 150, 160, -110)
    frac = (t * .45) % 1.2
    draw_path(c, route, '#E5484D', 1, 9, min(1, frac))
    c.restore()
    _pin(c, 160, -150 - 18 * abs(math.sin(t * 4)), A)


def v_mountain(c, t, p, A, B, seed):
    circle(c, -150 + 40 * math.sin(t * .5), -150, 70, A); glow(c, -150, -150, 160, A, .3)
    for k, (x0, h, col) in enumerate([(-320, 330, '#3D2C8D'), (-60, 420, '#5B3FD9'), (120, 300, '#2A1E66')]):
        pth = P(); pth.moveTo(x0, 260); pth.lineTo(x0 + 220, 260 - h); pth.lineTo(x0 + 440, 260); pth.close()
        fillp(c, pth, col)
        sn = P(); sn.moveTo(x0 + 220, 260 - h); sn.lineTo(x0 + 220 - 55, 260 - h + 80); sn.lineTo(x0 + 220 + 55, 260 - h + 80); sn.close()
        fillp(c, sn, WHITE, .9)
    for i in range(3):
        x = ((t * 50 + i * 230) % 760) - 380
        _cloud(c, x, -60 - i * 60, .6)


def _cloud(c, x, y, s):
    for dx, dy, r in [(-40, 0, 34), (0, -18, 44), (44, 0, 32), (0, 10, 36)]:
        circle(c, x + dx * s * 1.5, y + dy * s * 1.5, r * s * 1.5, WHITE, .9)


def v_tree(c, t, p, A, B, seed):
    sway = 5 * math.sin(t * 1.8)
    rrect(c, -26, 0, 52, 230, 18, '#8B5A2B')
    c.save(); c.rotate(sway)
    gr = ease_out(p)
    for i, (dx, dy, r) in enumerate([(0, -120, 150), (-120, -40, 110), (120, -40, 110), (-60, -210, 100), (70, -200, 100)]):
        rr = r * gr * (1 + .03 * math.sin(t * 3 + i))
        circle(c, dx, dy, rr, ['#2FBF71', '#25A35F', '#3DDC84'][i % 3])
    for i in range(5):  # falling leaves
        ph = (t * .4 + i / 5) % 1
        x = -200 + 90 * i + 30 * math.sin(t * 2 + i)
        c.drawOval(skia.Rect.MakeXYWH(x, -100 + 360 * ph, 26, 14), paint(A, 1 - ph))
    c.restore()


def v_bolt(c, t, p, A, B, seed):
    fl = 0.75 + 0.25 * abs(math.sin(t * 17)) if int(t * 4) % 3 else 1.0
    glow(c, 0, 0, 330, A, .5 * fl)
    pth = P()
    for i, (x, y) in enumerate([(40, -260), (-130, 30), (-10, 30), (-60, 260), (140, -60), (20, -60), (90, -260)]):
        (pth.moveTo if i == 0 else pth.lineTo)(x, y)
    pth.close()
    fillp(c, pth, A, fl); c.drawPath(pth, paint(WHITE, .9, 8))
    for i in range(8):
        a = _rng(seed, i) * 6.28 + t * 2; r = 200 + 80 * ((t * 1.5 + _rng(seed, i + 3)) % 1)
        line(c, r * math.cos(a), r * math.sin(a), (r + 40) * math.cos(a), (r + 40) * math.sin(a), B, .9, 7)


def v_thermo(c, t, p, A, B, seed):
    lvl = 0.5 + 0.4 * math.sin(t * 1.4)
    rrect(c, -50, -260, 100, 400, 50, WHITE, .95)
    circle(c, 0, 170, 90, WHITE, .95)
    circle(c, 0, 170, 68, '#FF3B3B')
    h = 360 * lvl
    rrect(c, -28, 150 - h, 56, h + 20, 28, '#FF3B3B')
    for i in range(6):
        line(c, 60, -220 + i * 60, 95, -220 + i * 60, WHITE, .7, 6)
    for i in range(4):  # heat squiggles
        x = -200 + (i % 2) * 400 * 0 + (-1) ** i * 40 - (160 if i < 2 else -160)
        sq = P(); sq.moveTo(x, 60)
        for k in range(1, 12):
            sq.lineTo(x + 16 * math.sin(k + t * 5), 60 - k * 22)
        c.drawPath(sq, paint(A, .7, 6))


# ---------------------------------------------------------------- animals
def v_fish(c, t, p, A, B, seed):
    for i in range(7):
        ph = (t * .5 + i / 7) % 1
        circle(c, 150 + 30 * math.sin(i + t * 2), 120 - 380 * ph, 8 + 6 * _rng(seed, i), B, (1 - ph) * .9, 4)
    x = 30 * math.sin(t * 1.3); y = 20 * math.sin(t * 2.1)
    c.save(); c.translate(x, y)
    wig = 18 * math.sin(t * 9)
    tail = P(); tail.moveTo(150, 0); tail.lineTo(260, -90 + wig); tail.lineTo(240, 0); tail.lineTo(260, 90 + wig); tail.close()
    fillp(c, tail, A)
    sh = skia.GradientShader.MakeLinear([(0, -110), (0, 110)], [rgb('#FFB703'), rgb('#FB5607')])
    c.drawOval(skia.Rect.MakeLTRB(-220, -115, 180, 115), skia.Paint(AntiAlias=True, Shader=sh))
    fin = P(); fin.moveTo(-40, -105); fin.lineTo(40, -175 + wig * .5); fin.lineTo(90, -95); fin.close(); fillp(c, fin, A)
    for k in range(3):
        arc(c, -30 + k * 55, 0, 70, -50, 100, WHITE, .35, 6)
    circle(c, -140, -25, 26, WHITE); circle(c, -146, -25, 13, DARK)
    c.restore()


def v_whale(c, t, p, A, B, seed):
    y = 30 + 15 * math.sin(t * 1.5)
    pth = P(); pth.moveTo(-260, y); pth.cubicTo(-260, y - 170, 120, y - 190, 200, y - 40)
    pth.cubicTo(240, y - 60, 280, y - 130, 300, y - 120); pth.cubicTo(290, y - 60, 280, y - 10, 240, y + 10)
    pth.cubicTo(180, y + 110, -260, y + 140, -260, y); pth.close()
    fillp(c, pth, '#3A7BD5')
    belly = P(); belly.moveTo(-250, y + 30); belly.cubicTo(-150, y + 120, 60, y + 110, 160, y + 40); belly.cubicTo(40, y + 70, -150, y + 70, -250, y + 30)
    fillp(c, belly, '#BFE3FF')
    circle(c, -170, y - 30, 14, DARK)
    for i in range(6):  # spout
        ph = (t * 1.2 + i / 6) % 1
        a = -1.57 + (i - 2.5) * .25
        r = 40 + 160 * ph
        circle(c, -120 + r * math.cos(a) * .6, y - 140 + r * math.sin(a), 14 * (1 - ph) + 4, B, 1 - ph)
    for k in range(2):
        wv = P(); wv.moveTo(-320, 210 + k * 50)
        for xx in range(-320, 330, 20):
            wv.lineTo(xx, 210 + k * 50 + 14 * math.sin(xx / 40 + t * 3 + k))
        c.drawPath(wv, paint(B, .7 - .3 * k, 8))


def v_bird(c, t, p, A, B, seed):
    for i in range(3):
        _cloud(c, ((-t * 80 + i * 260) % 780) - 390, 150 + 50 * (i % 2) - 220 * (i == 1), .55)
    flap = math.sin(t * 9)
    y = 15 * math.sin(t * 2)
    c.save(); c.translate(0, y)
    for sgn in (-1, 1):
        w = P(); w.moveTo(0, 0); w.cubicTo(sgn * 80, -60 - 110 * flap, sgn * 200, -80 - 160 * flap, sgn * 270, -40 - 150 * flap)
        w.cubicTo(sgn * 180, -10 - 30 * flap, sgn * 100, 20, 0, 30); w.close()
        fillp(c, w, '#FFFFFF' if sgn < 0 else '#E6ECF7')
    c.drawOval(skia.Rect.MakeLTRB(-70, -30, 90, 50), paint(A))
    circle(c, 95, -15, 38, A); circle(c, 105, -24, 8, DARK)
    bk = P(); bk.moveTo(128, -18); bk.lineTo(170, -5); bk.lineTo(128, 4); bk.close(); fillp(c, bk, '#FF7A00')
    c.restore()


def v_octopus(c, t, p, A, B, seed):
    y = 20 * math.sin(t * 1.6)
    col = '#FF4F8B'
    for k in range(8):
        x0 = -110 + k * 31
        pth = P(); pth.moveTo(x0, y + 10)
        for s in range(1, 14):
            pth.lineTo(x0 + (k - 3.5) * s * 6 + 22 * math.sin(s * .5 + t * 4 + k), y + 10 + s * 18)
        c.drawPath(pth, paint(col, 1, 30 - 0 * k))
    c.drawOval(skia.Rect.MakeLTRB(-150, y - 230, 150, y + 50), paint(col))
    for sx in (-55, 55):
        circle(c, sx, y - 60, 30, WHITE); circle(c, sx + 6 * math.sin(t * 2), y - 60, 15, DARK)
    for i in range(3):
        circle(c, -60 + i * 50, y - 160, 14, '#FF8FB4', .8)


def v_bee(c, t, p, A, B, seed):
    x = 120 * math.sin(t * 1.2); y = 60 * math.sin(t * 2.4)
    for i in range(10):  # dotted trail
        tt = t - i * .08
        circle(c, 120 * math.sin(tt * 1.2), 60 * math.sin(tt * 2.4) + 40, 6, WHITE, .5 - i * .04)
    c.save(); c.translate(x, y)
    fl = abs(math.sin(t * 22))
    for sgn in (-1, 1):
        c.drawOval(skia.Rect.MakeXYWH(-40 + sgn * 30 - 45, -130 - 30 * fl, 90, 120 + 20 * fl), paint('#DFF6FF', .75))
    c.drawOval(skia.Rect.MakeLTRB(-130, -60, 130, 70), paint(A))
    c.save(); c.clipPath(_oval(-130, -60, 130, 70), doAntiAlias=True)
    for k in range(3):
        rrect(c, -60 + k * 60, -70, 28, 150, 0, DARK)
    c.restore()
    circle(c, -150, 0, 50, DARK); circle(c, -165, -10, 12, WHITE)
    st = P(); st.moveTo(128, -8); st.lineTo(175, 4); st.lineTo(128, 18); st.close(); fillp(c, st, DARK)
    c.restore()


def _oval(l, t_, r, b):
    p = P(); p.addOval(skia.Rect.MakeLTRB(l, t_, r, b)); return p


def v_paws(c, t, p, A, B, seed):
    n = 6
    for i in range(n):
        ph = ((t * 1.4) % 5.0) - i * .5
        a = clamp(ph) if ph < 3 else clamp(4 - ph)
        if a <= 0:
            continue
        x = -220 + i * 90; y = 200 - i * 80 + (30 if i % 2 else -30)
        c.save(); c.translate(x, y); c.rotate(-40)
        c.drawOval(skia.Rect.MakeXYWH(-34, -10, 68, 58), paint(A if i % 2 else WHITE, a))
        for k, (dx, dy) in enumerate([(-38, -30), (-13, -50), (13, -50), (38, -30)]):
            circle(c, dx, dy, 14, A if i % 2 else WHITE, a)
        c.restore()


def v_dino(c, t, p, A, B, seed):
    y = 8 * math.sin(t * 4)
    col = '#3DDC84'
    pth = P(); pth.moveTo(-300, 40 + y); pth.cubicTo(-150, -20 + y, -60, -60 + y, 40, -60 + y)
    pth.cubicTo(70, -160 + y, 100, -230 + y, 170, -230 + y); pth.cubicTo(250, -230 + y, 270, -190 + y, 260, -170 + y)
    pth.cubicTo(200, -160 + y, 160, -150 + y, 150, -100 + y); pth.cubicTo(150, 20 + y, 100, 80 + y, 20, 90 + y)
    pth.cubicTo(-100, 90 + y, -220, 70 + y, -300, 40 + y); pth.close()
    fillp(c, pth, col)
    leg = 20 * math.sin(t * 8)
    rrect(c, -60 + leg, 60 + y, 44, 140, 20, '#2FBF71'); rrect(c, 40 - leg, 60 + y, 44, 140, 20, '#25A35F')
    circle(c, 200, -200 + y, 10, DARK)
    for i in range(5):
        sp = P(); x0 = -150 + i * 45; yy = -35 - i * 6 + y
        sp.moveTo(x0, yy); sp.lineTo(x0 + 18, yy - 40); sp.lineTo(x0 + 36, yy); sp.close(); fillp(c, sp, A)
    rrect(c, -340, 200, 680, 10, 5, WHITE, .4)


# ---------------------------------------------------------------- body
def _heart_path(s=1.0):
    pth = P(); pth.moveTo(0, 150 * s); pth.cubicTo(-120 * s, 60 * s, -220 * s, -10 * s, -200 * s, -100 * s)
    pth.cubicTo(-180 * s, -190 * s, -60 * s, -200 * s, 0, -110 * s); pth.cubicTo(60 * s, -200 * s, 180 * s, -190 * s, 200 * s, -100 * s)
    pth.cubicTo(220 * s, -10 * s, 120 * s, 60 * s, 0, 150 * s); pth.close(); return pth


def v_heart(c, t, p, A, B, seed):
    beat = (t * 1.6) % 1
    s = 1 + 0.12 * math.exp(-beat * 9) + 0.06 * math.exp(-max(0, beat - .22) * 9) * (beat > .22)
    glow(c, 0, -20, 300 * s, '#FF3B5C', .45)
    c.save(); c.translate(0, -40); c.scale(s, s)
    sh = skia.GradientShader.MakeLinear([(0, -200), (0, 150)], [rgb('#FF6B81'), rgb('#D90429')])
    c.drawPath(_heart_path(), skia.Paint(AntiAlias=True, Shader=sh))
    c.drawOval(skia.Rect.MakeXYWH(-150, -150, 60, 40), paint(WHITE, .45))
    c.restore()
    ecg = P(); ecg.moveTo(-320, 220)
    pts = [(-120, 220), (-90, 180), (-60, 220), (-30, 120), (0, 300), (30, 220), (320, 220)]
    for x, y in pts:
        ecg.lineTo(x, y)
    draw_path(c, ecg, B, 1, 8, ((t * .9) % 1.0) * 1.0 + .001)


def v_brain(c, t, p, A, B, seed):
    glow(c, 0, 0, 300, '#FF7AC8', .35)
    s = 1 + .03 * math.sin(t * 3)
    g.draw_icon(c, 'brain', 0, -10, 440 * s, 1, t, '#FF9AD5', A)
    for i in range(8):  # neural sparks
        a = _rng(seed, i) * 6.28; r = 170 + 40 * math.sin(t * 3 + i)
        circle(c, r * math.cos(a), r * math.sin(a) * .8 - 10, 9, B, .5 + .5 * math.sin(t * 6 + i))


def v_body(c, t, p, A, B, seed):
    col = '#9FB4FF'
    circle(c, 0, -210, 62, col, .9)
    rrect(c, -105, -140, 210, 260, 70, col, .9)
    rrect(c, -165, -130, 50, 220, 25, col, .8); rrect(c, 115, -130, 50, 220, 25, col, .8)
    rrect(c, -90, 110, 70, 200, 30, col, .8); rrect(c, 20, 110, 70, 200, 30, col, .8)
    beat = (t * 1.5) % 1
    sc = .25 * (1 + .15 * math.exp(-beat * 8))
    glow(c, -25, -60, 120, '#FF3B5C', .6)
    c.save(); c.translate(-25, -60); c.scale(sc, sc)
    fillp(c, _heart_path(), '#FF3B5C'); c.restore()
    # scanning line
    yy = -280 + 600 * ((t * .5) % 1)
    rrect(c, -220, yy, 440, 6, 3, B, .8); glow(c, 0, yy, 160, B, .2)


def v_eye(c, t, p, A, B, seed):
    bl = (t * .6) % 1
    open_ = 1 - (math.sin(min(1, max(0, (bl - .85) / .15)) * math.pi))
    h = 150 * max(.05, open_)
    e = P(); e.moveTo(-280, 0); e.quadTo(0, -2 * h, 280, 0); e.quadTo(0, 2 * h, -280, 0); e.close()
    fillp(c, e, WHITE)
    c.save(); c.clipPath(e, doAntiAlias=True)
    px = 90 * math.sin(t * 1.3); py = 30 * math.sin(t * 1.9)
    sh = skia.GradientShader.MakeRadial((px, py), 110, [rgb('#7CF0FF'), rgb('#1B6CFF')])
    c.drawCircle(px, py, 110, skia.Paint(AntiAlias=True, Shader=sh))
    circle(c, px, py, 50, DARK); circle(c, px - 30, py - 30, 18, WHITE, .9)
    c.restore()
    c.drawPath(e, paint(A, 1, 10))


def v_bone(c, t, p, A, B, seed):
    c.save(); c.rotate(-30 + 12 * math.sin(t * 1.5))
    rrect(c, -200, -38, 400, 76, 30, '#F5F0E1')
    for sx in (-1, 1):
        circle(c, sx * 215, -45, 60, '#F5F0E1'); circle(c, sx * 215, 45, 60, '#F5F0E1')
    c.restore()
    sparkles(c, t, seed, 8, 290, A)


# ---------------------------------------------------------------- abstract / numbers
def v_clock(c, t, p, A, B, seed):
    R = 230
    glow(c, 0, 0, 330, B, .3)
    circle(c, 0, 0, R, '#101830'); circle(c, 0, 0, R, A, 1, 16)
    for i in range(12):
        a = i * math.pi / 6
        line(c, (R - 40) * math.sin(a), -(R - 40) * math.cos(a), (R - 18) * math.sin(a), -(R - 18) * math.cos(a), WHITE, .9, 10 if i % 3 == 0 else 5)
    ha = t * 1.2; ma = t * 9
    line(c, 0, 0, 110 * math.sin(ha), -110 * math.cos(ha), WHITE, 1, 18)
    line(c, 0, 0, 170 * math.sin(ma), -170 * math.cos(ma), B, 1, 10)
    circle(c, 0, 0, 18, A)
    # sweep trail
    arc(c, 0, 0, R + 40, -90, (t * 120) % 360, A, .6, 10)


def v_hourglass(c, t, p, A, B, seed):
    c.save(); c.rotate(6 * math.sin(t * 1.3))
    rrect(c, -170, -250, 340, 26, 10, A); rrect(c, -170, 224, 340, 26, 10, A)
    gl = P(); gl.moveTo(-140, -224); gl.lineTo(140, -224); gl.lineTo(20, 0); gl.lineTo(140, 224); gl.lineTo(-140, 224); gl.lineTo(-20, 0); gl.close()
    fillp(c, gl, WHITE, .15); c.drawPath(gl, paint(WHITE, .9, 8))
    lv = (t * .15) % 1
    top = P(); y0 = -200 + 190 * lv; w = 120 * (1 - (y0 + 224) / 224)
    top.moveTo(-max(5, (200 - (y0 + 200)) * .6 + 10), y0)
    top.moveTo(-120 * (1 - lv) - 10, y0); top.lineTo(120 * (1 - lv) + 10, y0); top.lineTo(0, -10); top.close()
    fillp(c, top, A)
    bot = P(); h = 30 + 150 * lv
    bot.moveTo(-130, 215); bot.lineTo(130, 215); bot.lineTo(0, 215 - h); bot.close(); fillp(c, bot, A)
    for i in range(5):
        circle(c, 0, -5 + ((t * 3 + i / 5) % 1) * (215 - h), 5, A)
    c.restore()


def v_chart(c, t, p, A, B, seed):
    base = 220
    vals = [.3, .45, .4, .65, .8, 1.0]
    for i, v in enumerate(vals):
        gp = ease_out(clamp((t * 1.6 - i * .12)))
        h = 400 * v * gp * (1 + .03 * math.sin(t * 3 + i))
        rrect(c, -290 + i * 98, base - h, 70, h, 12, B if i < 5 else A, .95)
    ar = P(); ar.moveTo(-290, 120); ar.lineTo(-100, 20); ar.lineTo(30, 60); ar.lineTo(260, -200)
    fr = clamp(t * .8)
    draw_path(c, ar, WHITE, 1, 14, fr)
    if fr > .95:
        hd = P(); hd.moveTo(200, -205); hd.lineTo(275, -215); hd.lineTo(255, -140); hd.close(); fillp(c, hd, WHITE)
    rrect(c, -320, base, 640, 8, 4, WHITE, .6)


def v_arrows(c, t, p, A, B, seed):
    for i in range(3):
        ph = (t * .9 + i / 3) % 1
        y = 220 - 460 * ph
        a = math.sin(ph * math.pi)
        s = .7 + .3 * i / 2
        pth = P(); pth.moveTo(0, y - 110 * s); pth.lineTo(120 * s, y); pth.lineTo(50 * s, y); pth.lineTo(50 * s, y + 110 * s)
        pth.lineTo(-50 * s, y + 110 * s); pth.lineTo(-50 * s, y); pth.lineTo(-120 * s, y); pth.close()
        fillp(c, pth, A if i == 1 else B, a)


def v_coin(c, t, p, A, B, seed):
    sx = abs(math.cos(t * 2.5)) * .9 + .1
    glow(c, 0, 0, 300, A, .4)
    c.save(); c.scale(sx, 1)
    circle(c, 0, 0, 200, '#E0A800'); circle(c, 0, 0, 170, A); circle(c, 0, 0, 170, '#E0A800', 1, 10)
    text(c, '$', 0, 85, 240, 'display', '#B07F00', 1, 'center')
    c.restore()
    sparkles(c, t, seed, 8, 280, WHITE)


def v_question(c, t, p, A, B, seed):
    sparkles(c, t, seed, 10, 280, B)
    b = 20 * abs(math.sin(t * 3))
    c.save(); c.rotate(8 * math.sin(t * 2))
    g.stroke_text(c, '?', 0, 150 - b, 480, 'display', A, DARK, 18, 'center')
    c.restore()


def v_compare(c, t, p, A, B, seed):
    s1 = 1 + .05 * math.sin(t * 3)
    circle(c, -150, 40, 70 * s1, B)
    circle(c, 130, 0, 190 * (1 + .03 * math.sin(t * 2 + 1)), A)
    g.stroke_text(c, 'VS', -10, -170, 90, 'display', WHITE, DARK, 10, 'center')


def v_food(c, t, p, A, B, seed):
    c.save(); c.rotate(8 * math.sin(t * 2))
    ap = P(); ap.moveTo(0, -120); ap.cubicTo(80, -190, 220, -150, 210, -10); ap.cubicTo(200, 120, 110, 210, 40, 190)
    ap.cubicTo(15, 180, -15, 180, -40, 190); ap.cubicTo(-110, 210, -200, 120, -210, -10); ap.cubicTo(-220, -150, -80, -190, 0, -120); ap.close()
    fillp(c, ap, '#FF3B3B')
    c.drawOval(skia.Rect.MakeXYWH(-150, -110, 50, 80), paint(WHITE, .45))
    rrect(c, -8, -200, 16, 90, 8, '#8B5A2B')
    lf = P(); lf.moveTo(10, -170); lf.cubicTo(60, -240, 130, -220, 140, -190); lf.cubicTo(100, -150, 40, -150, 10, -170); fillp(c, lf, '#3DDC84')
    c.restore()
    sparkles(c, t, seed, 6, 290, A)


def v_rocket(c, t, p, A, B, seed):
    y = 20 * math.sin(t * 5)
    for i in range(14):  # exhaust
        ph = (t * 2 + i / 14) % 1
        circle(c, (_rng(seed, i) - .5) * 60 * ph, 170 + 260 * ph + y, 30 * (1 - ph) + 6, A if i % 2 else '#FF7A00', 1 - ph)
    c.save(); c.translate(0, y); c.rotate(2 * math.sin(t * 7))
    body = P(); body.moveTo(0, -250); body.cubicTo(90, -170, 90, 50, 70, 160); body.lineTo(-70, 160); body.cubicTo(-90, 50, -90, -170, 0, -250); body.close()
    fillp(c, body, WHITE)
    for sx in (-1, 1):
        f = P(); f.moveTo(sx * 70, 40); f.lineTo(sx * 140, 170); f.lineTo(sx * 60, 160); f.close(); fillp(c, f, '#E5484D')
    circle(c, 0, -80, 42, B); circle(c, 0, -80, 42, DARK, 1, 10)
    c.restore()
    for i in range(10):
        x = (_rng(seed, i) - .5) * 640; yy = ((t * 400 + _rng(seed, i + 5) * 700) % 700) - 350
        line(c, x, yy, x, yy - 40, WHITE, .5, 4)


def v_icon(name):
    def fn(c, t, p, A, B, seed):
        glow(c, 0, 0, 300, B, .3)
        c.save(); c.rotate(t * 20)
        for i in range(24):
            if i % 2 == 0:
                arc(c, 0, 0, 260, i * 15, 9, B, .6, 8)
        c.restore()
        g.draw_icon(c, name, 0, 0, 380 * (1 + .04 * math.sin(t * 3)), 1, t, WHITE, A)
        sparkles(c, t, seed, 6, 300, A)
    return fn


VISUALS = {
    'planet': v_planet, 'stars': v_stars, 'sun': v_sun, 'atom': v_atom, 'waves': v_waves, 'drop': v_drop,
    'globe': v_globe, 'map': v_map, 'mountain': v_mountain, 'tree': v_tree, 'bolt': v_bolt, 'thermo': v_thermo,
    'fish': v_fish, 'whale': v_whale, 'bird': v_bird, 'octopus': v_octopus, 'bee': v_bee, 'paws': v_paws, 'dino': v_dino,
    'heart': v_heart, 'brain': v_brain, 'body': v_body, 'eye': v_eye, 'bone': v_bone,
    'clock': v_clock, 'hourglass': v_hourglass, 'chart': v_chart, 'arrows': v_arrows, 'coin': v_coin,
    'question': v_question, 'compare': v_compare, 'food': v_food, 'rocket': v_rocket,
    'lightbulb': v_icon('lightbulb'), 'book': v_icon('book'), 'people': v_icon('people'), 'flask': v_icon('flask'),
    'magnifier': v_icon('magnifier'), 'phone': v_icon('phone'), 'calendar': v_icon('calendar'), 'building': v_icon('building'),
    'warning': v_icon('warning'), 'check': v_icon('check'),
    'robot': v_icon('robot'), 'chat': v_icon('chat'), 'cube': None,
}

KEYWORDS = [
    ('planet', 'planet saturn jupiter mars venus mercury neptune uranus pluto orbit solar_system moon lunar'),
    ('stars', 'star stars galaxy universe space cosmos light_year light_year black_hole nebula milky deep_space warp'),
    ('sun', 'sun solar sunlight sunshine daylight summer'),
    ('rocket', 'rocket launch astronaut nasa spacecraft shuttle mission iss space_station'),
    ('atom', 'atom atoms electron proton molecule particle quantum physics chemistry element nuclear'),
    ('waves', 'ocean sea wave waves tide surf beach underwater deep_sea'),
    ('drop', 'water droplet raindrop rain liquid drink sweat tear river lake lakes brine salty salt ice melt'),
    ('globe', 'earth globe world planet earth country countries continent equator'),
    ('map', 'map route travel journey island city cities road border migration miles kilometers distance'),
    ('mountain', 'mountain everest volcano peak hill cliff rock rocks glacier'),
    ('tree', 'tree trees forest plant plants leaf leaves flower seed wood grow oxygen'),
    ('bolt', 'lightning electric electricity energy power bolt shock storm thunder volt battery'),
    ('thermo', 'hot cold temperature heat degrees celsius fahrenheit fire freeze frozen warm'),
    ('fish', 'fish shark goldfish salmon swim fins gills coral'),
    ('whale', 'whale whales dolphin blue_whale mammal marine'),
    ('bird', 'bird birds fly flying wings feather flamingo crow parrot owl penguin eagle'),
    ('octopus', 'octopus squid tentacle tentacles jellyfish'),
    ('bee', 'bee bees insect insects ant ants honey butterfly bug bugs mosquito'),
    ('paws', 'wombat wombats marsupial mouse mice cat cats dog dogs animal animals paw paws pet pets footprint tracks lion tiger elephant cow'),
    ('dino', 'dinosaur dinosaurs t-rex fossil prehistoric extinct reptile crocodile lizard'),
    ('heart', 'heart hearts heartbeat blood pulse beats cardio love'),
    ('brain', 'brain cerebellum predict prediction predicts tickle tickling mind memory neuron neurons think thinking dream sleep nerve'),
    ('body', 'body human organ organs stomach skin lungs liver cells cell muscle blood vessels'),
    ('eye', 'eye eyes see vision sight blink color colours colors look'),
    ('bone', 'bone bones skeleton skull teeth tooth'),
    ('clock', 'clock stopwatch delay time seconds second minute minutes hours hour day days fast speed'),
    ('hourglass', 'years ancient history century centuries old ago age era'),
    ('chart', 'percent growth increase data statistics chart graph more_than record rate'),
    ('arrows', 'rise rising higher bigger taller grow upward'),
    ('coin', 'money dollar dollars cost price coin gold rich worth pay million billion'),
    ('compare', 'compare side_by_side versus vs bigger_than smaller_than size larger tiny huge'),
    ('food', 'food eat eating apple fruit banana honey sugar taste cook pizza chocolate'),
    ('lightbulb', 'lightbulb idea invent invented invention discover discovery genius'),
    ('book', 'book books read word words language write letter alphabet'),
    ('people', 'people person humans everyone population crowd'),
    ('flask', 'scientist scientists experiment lab study research test'),
    ('magnifier', 'search found find detect hidden secret tiny microscopic'),
    ('phone', 'phone smartphone screen internet app computer'),
    ('calendar', 'calendar date birthday week month year'),
    ('building', 'building tower city skyscraper house castle pyramid'),
    ('warning', 'danger dangerous deadly poison toxic warning risk'),
    ('cube', 'cube cubes cubic square block box poop droppings'),
    ('robot', 'robot robotic machine arm'),
    ('chat', 'speech_bubble bubble comment comments message'),
    ('question', 'why what mystery weird strange question really'),
]
_KW = [(k, [w for w in re.split(r'\s{1,}', v) if w]) for k, v in KEYWORDS]

CATEGORY_DEFAULT = {
    'space': ['stars', 'planet', 'rocket', 'sun'], 'animals': ['paws', 'fish', 'bird', 'bee'],
    'ocean': ['waves', 'fish', 'whale', 'drop'], 'body': ['body', 'heart', 'brain', 'eye'], 'human': ['body', 'brain', 'heart', 'eye'],
    'history': ['hourglass', 'building', 'map', 'book'], 'science': ['atom', 'flask', 'bolt', 'lightbulb'],
    'food': ['food', 'coin', 'drop'], 'nature': ['tree', 'mountain', 'sun', 'drop'], 'earth': ['globe', 'mountain', 'waves'],
    'tech': ['phone', 'bolt', 'lightbulb'], 'psych': ['brain', 'lightbulb', 'question', 'eye'], 'language': ['book', 'globe', 'people'],
}


def category_defaults(cat):
    cat = (cat or '').lower()
    for k, v in sorted(CATEGORY_DEFAULT.items(), key=lambda kv: kv[0] not in ('psych', 'body', 'human')):
        if k in cat:
            return v
    return ['question', 'lightbulb', 'stars', 'atom']


def choose(desc, line_en='', category='', avoid=()):
    """Score each visual by keyword hits in the beat description (x3) and line text (x1). -> ranked list."""
    d = ' ' + re.sub(r'[^a-z0-9\- ]', ' ', (desc or '').lower()) + ' '
    l = ' ' + re.sub(r'[^a-z0-9\- ]', ' ', (line_en or '').lower()) + ' '
    scores = {}
    for k, words in _KW:
        s = 0
        for w in words:
            w = w.replace('_', ' ')
            pat = ' ' + w
            # allow plural/suffix match for single words
            if (' ' + w + ' ') in d or (len(w) > 3 and pat in d):
                s += 3 + (1 if ' ' in w else 0)
            if (' ' + w + ' ') in l or (len(w) > 3 and pat in l):
                s += 1
        if s:
            scores[k] = s
    ranked = sorted(scores, key=lambda k: -scores[k])
    choose.last_scores = scores
    for k in category_defaults(category):
        if k not in ranked:
            ranked.append(k)
    pref = [k for k in ranked if k not in avoid]
    return pref or ranked


def v_cube(c, t, p, A, B, seed):
    """Isometric cube spinning on its vertical axis, bouncing."""
    b = 30 * abs(math.sin(t * 3))
    c.save(); c.translate(0, 40 - b)
    a = t * 1.3
    R = 170
    top = [(R * math.cos(a + k * math.pi / 2), R * 0.5 * math.sin(a + k * math.pi / 2) - 120) for k in range(4)]
    bot = [(x, y + 240) for x, y in top]
    rrect(c, -170, 190 + b, 340, 26, 13, '#000000', .25)
    faces = []
    for k in range(4):
        j = (k + 1) % 4
        depth = top[k][1] + top[j][1]
        faces.append((depth, [top[k], top[j], bot[j], bot[k]], k))
    cols = ['#9C6B3E', '#7A4F2A', '#B98352', '#6B4423']
    for depth, pts, k in sorted(faces):
        pth = P(); pth.moveTo(*pts[0])
        for q in pts[1:]:
            pth.lineTo(*q)
        pth.close(); fillp(c, pth, cols[k]); c.drawPath(pth, paint(DARK, .5, 5))
    pth = P(); pth.moveTo(*top[0])
    for q in top[1:]:
        pth.lineTo(*q)
    pth.close(); fillp(c, pth, '#C99560'); c.drawPath(pth, paint(A, .9, 6))
    c.restore()
    sparkles(c, t, seed, 6, 290, A)


VISUALS['cube'] = v_cube
