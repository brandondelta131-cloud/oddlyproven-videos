"""Reusable animated visual types + automatic scene -> visual mapping.

Every visual draws inside the CONTENT box (y ~130..850) so the bottom band stays free
for burned-in subtitles. A scene may carry an optional "type" and "spec" (merged from a
<name>_visuals.json override file) for precise data; otherwise the type and its content
are inferred from on_screen_text + the visual description.
"""
import math
import random
import re
from gfx import *  # noqa

TOP, BOTTOM = 130, 845
CX = W / 2

NUM_RE = re.compile(r'(?<![\w.])([<>~≈+\-−]?)(\$?)(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(%|x\b|×|k\b|K\b|M\b|B\b|percent\b)?')
YEAR_RE = re.compile(r'\b(1[89]\d{2}|20\d{2})\b')
COLORS = {'amber': AMBER, 'teal': TEAL, 'gray': GRAY, 'grey': GRAY, 'red': RED, 'white': WHITE, 'muted': MUTED}


def col_of(v, default=AMBER):
    if not v:
        return default
    return COLORS.get(v, v if str(v).startswith('#') else default)


# ---------------------------------------------------------------- parsing helpers
def norm_items(ost):
    if ost is None:
        return []
    if isinstance(ost, dict):
        ost = [str(v) for v in ost.values()]
    if isinstance(ost, str):
        parts = re.split(r'\s*(?:\n|\s\|\s|;\s|•|\s·\s)\s*', ost)
    else:
        parts = []
        for o in ost:
            parts += norm_items(o) if not isinstance(o, str) else [o]
    return [p.strip() for p in parts if p and p.strip()]


def find_numbers(s):
    out = []
    for m in NUM_RE.finditer(s):
        pre, cur, num, unit = m.groups()
        raw = num.replace(',', '')
        try:
            v = float(raw)
        except ValueError:
            continue
        if not unit and YEAR_RE.fullmatch(num):
            continue
        if unit == 'percent':
            unit = '%'
        sign = ''
        if pre in ('-', '−'):
            v = -v; pre = ''
        elif pre == '+':
            sign = '+'; pre = ''
        out.append(dict(value=v, prefix=(pre or '') + (cur or ''), sign=sign, unit=unit or '', span=m.span(),
                        decimals=len(raw.split('.')[1]) if '.' in raw else 0, raw=m.group(0).strip()))
    return out


def mknum(value, unit='', prefix='', sign='', decimals=None):
    if decimals is None:
        decimals = 0 if float(value).is_integer() else len(str(value).split('.')[1])
    return dict(value=float(value), unit=unit, prefix=prefix, sign=sign, decimals=decimals, raw=str(value), span=(0, 0))


def fmt_num(v, n, frac):
    val = n['value'] * frac
    if n['decimals']:
        s = f"{abs(val):.{n['decimals']}f}"
    elif abs(n['value']) >= 1000:
        s = f"{int(round(abs(val))):,}"
    else:
        s = str(int(round(abs(val))))
    unit = n['unit']
    if unit in ('x', '×'):
        unit = '×'
    sign = '−' if val < 0 and s.strip('0.,') else (n.get('sign') or '')
    return n['prefix'] + sign + s + unit


def strip_num(s, n):
    a, b = n['span']
    r = (s[:a] + s[b:]).strip(' :-–—,()')
    return re.sub(r'\s{2,}', ' ', r)


def chip(c, s, x, y, color=AMBER, alpha=1.0, align='center', size=24, fill=NAVY):
    """Pill-shaped tag. (x,y) = anchor at vertical center."""
    if alpha <= 0.01 or not s:
        return 0
    w = measure(s, size, 'semibold') + 44
    h = size * 1.9
    x0 = x - w / 2 if align == 'center' else (x - w if align == 'right' else x)
    rrect(c, x0, y - h / 2, w, h, h / 2, fill, .85 * alpha)
    rrect(c, x0, y - h / 2, w, h, h / 2, color, alpha, 3)
    text(c, s, x0 + w / 2, y + size * .36, size, 'semibold', color, alpha, 'center')
    return w


def label(c, s, x, y, color=TEAL, alpha=1, align='left', size=22):
    text(c, s.upper(), x, y, size, 'bold', color, alpha, align, tracking=3.5)


# ---------------------------------------------------------------- base
class Visual:
    kind = 'base'

    def __init__(self, scene, items, dur, beats, mirror=False, index=0):
        self.scene, self.items, self.dur, self.beats, self.mirror, self.index = scene, items, dur, beats, mirror, index
        self.spec = scene.get('spec') or {}
        self.desc = (scene.get('visual') or '')
        self.alltext = ' '.join(items) + ' ' + self.desc
        if 'mirror' in self.spec:
            self.mirror = bool(self.spec['mirror'])
        self.setup()

    def setup(self):
        pass

    def beat(self, i, default=None):
        if i is None:
            return default if default is not None else 0
        if 0 <= i < len(self.beats):
            return self.beats[i]
        return default if default is not None else (self.beats[-1] if self.beats else 0)

    def note(self, c, t, y=200, x=CX, align='center', color=AMBER):
        n = self.spec.get('note')
        if n:
            st = self.beat(self.spec.get('note_at'), 1.0) + .2
            p = ease_back(prog(t, st, .5))
            if p > .01:
                c.save(); c.translate(x, y); c.scale(p, p)
                chip(c, n, 0, 0, col_of(self.spec.get('note_color'), color), clamp(p), align)
                c.restore()

    def draw(self, c, t):
        raise NotImplementedError


# ---------------------------------------------------------------- chapter card
class ChapterCard(Visual):
    kind = 'chapter'

    def setup(self):
        self.num = self.scene.get('_chapter_num', 1)
        self.title = self.scene.get('_chapter_title') or self.scene.get('chapter', '')

    def draw(self, c, t):
        d = self.dur
        out = ease_in_out(prog(t, d - .45, .45))
        a = ease_out(prog(t, .05, .5)) * (1 - out)
        cy = 470
        text(c, f'{self.num:02d}', CX, cy + 190, 520, 'display', '#1C2C50', .55 * a, 'center')
        w = 1100 * ease_in_out(prog(t, 0, .7))
        x0 = CX - 550 + 1100 * out
        rrect(c, x0, cy + 70, max(0, w - 1100 * out), 6, 3, AMBER, 1)
        lines, sz = fit_wrap(self.title, 1500, 2, 92, 'display', 56)
        first_top = cy + 30 - (len(lines) - 1) * sz * 1.1 - sz * .75
        label(c, f'Chapter {self.num:02d}', CX, first_top - 40, TEAL, a, 'center', 28)
        for i, ln in enumerate(lines):
            yy = cy + 30 - (len(lines) - 1 - i) * sz * 1.1 + 30 * (1 - ease_out(prog(t, .1 + i * .08, .6)))
            text(c, ln, CX, yy, sz, 'display', WHITE, a, 'center')
        for i in range(12):
            tp = prog(t, .2 + i * .03, .3)
            line(c, CX - 550 + i * 100, cy + 100, CX - 550 + i * 100, cy + 100 + 14 * ease_out(tp), DIM, a, 3)


# ---------------------------------------------------------------- big number
class BigNumber(Visual):
    kind = 'big_number'

    def setup(self):
        sp = self.spec
        if 'value' in sp:
            self.n = mknum(sp['value'], sp.get('unit', ''), sp.get('prefix', ''), sp.get('sign', ''))
            self.caption = sp.get('caption', '')
            self.sub = sp.get('sub', '')
        else:
            best = None
            for it in self.items:
                ns = find_numbers(it)
                if ns:
                    best = (it, ns[0]); break
            self.src, self.n = best
            a, b = self.n['span']
            cap = strip_num(self.src, self.n) if (a <= 2 or b >= len(self.src) - 1) else self.src
            others = [i for i in self.items if i != self.src]
            self.caption = cap or (others[0] if others else '')
            self.sub = others[0] if cap and others else ''
        self.ring = sp.get('ring', 'fraction' if self.n['unit'] == '%' and 0 < self.n['value'] <= 100 else 'full')
        self.icon = sp.get('icon')

    def draw(self, c, t):
        n = self.n
        cx = 640 if not self.mirror else 1280
        tx = 1110 if not self.mirror else 170
        cy = 480
        p = ease_out(prog(t, .2, 1.6))
        a = ease_out(prog(t, 0, .5))
        R = 250
        arc(c, cx, cy, R, 0, 359.9, DIM, .5 * a, 16)
        frac = n['value'] / 100 if self.ring == 'fraction' else 1
        sweep = 360 * frac * p
        glow(c, cx, cy, R + 80, AMBER, .10 * a)
        arc(c, cx, cy, R, -90, sweep, AMBER, a, 18)
        ang = math.radians(-90 + sweep)
        circle(c, cx + R * math.cos(ang), cy + R * math.sin(ang), 14 * p, WHITE, a)
        if self.ring == 'full':  # tick marks for counters
            for k in range(60):
                aa = math.radians(k * 6 - 90)
                on = k / 60 <= p
                line(c, cx + (R - 40) * math.cos(aa), cy + (R - 40) * math.sin(aa), cx + (R - 54) * math.cos(aa), cy + (R - 54) * math.sin(aa),
                     AMBER if on else DIM, a * (.9 if on else .5), 3)
        s = fmt_num(n['value'], n, p)
        sz = 190 if len(s) <= 4 else 150 if len(s) <= 6 else 110
        text(c, s, cx, cy + sz * 0.36, sz, 'display', WHITE, a, 'center')
        ca = ease_out(prog(t, .6, .6))
        dx = (40 if not self.mirror else -40) * (1 - ca)
        lines, sz2 = fit_wrap(self.caption, 640, 4, 60, 'bold', 38)
        y = 470 - (len(lines) - 1) * sz2 * 0.6 - (40 if self.sub else 0)
        for i, ln in enumerate(lines):
            text(c, ln, tx + dx, y + i * sz2 * 1.18, sz2, 'bold', WHITE, ca)
        y += (len(lines) - 1) * sz2 * 1.18 + 44
        line(c, tx, y, tx + 120, y, AMBER, ca, 6, ease_out(prog(t, .9, .5)))
        if self.sub:
            sa = ease_out(prog(t, self.beat(self.spec.get('sub_at', 1), 1.4), .6))
            sl, ss = fit_wrap(self.sub, 640, 3, 34, 'medium', 26)
            for i, ln in enumerate(sl):
                text(c, ln, tx, y + 60 + i * ss * 1.3, ss, 'medium', MUTED, sa)


# ---------------------------------------------------------------- change A -> B
class Change(Visual):
    kind = 'change'

    def setup(self):
        sp = self.spec
        if 'to' in sp:
            self.a = mknum(sp['from'], sp.get('unit', '')); self.b = mknum(sp['to'], sp.get('unit', ''))
        else:
            ns = [n for it in self.items for n in find_numbers(it)]
            self.a, self.b = ns[0], ns[1]
        self.caption = sp.get('caption') or next((strip_num(i, find_numbers(i)[0]) for i in self.items if find_numbers(i)), '')
        self.la, self.lb = sp.get('from_label', 'before'), sp.get('to_label', 'after')

    def draw(self, c, t):
        a = ease_out(prog(t, 0, .5))
        st = self.beat(self.spec.get('at'), .4)
        pa = ease_out(prog(t, st - .3, .6))
        text(c, fmt_num(self.a['value'], self.a, 1), 560, 520, 170, 'display', GRAY, pa, 'center')
        label(c, self.la, 560, 600, GRAY, pa, 'center', 24)
        arrow(c, 760, 460, 1080, 460, AMBER, 1, 10, ease_in_out(prog(t, st, .7)), 34)
        pb = ease_out(prog(t, st + .5, 1.0))
        glow(c, 1340, 460, 300, AMBER, .14 * pb)
        sb = fmt_num(self.b['value'], self.b, pb)
        text(c, sb, 1340, 545, 250, 'display', AMBER, clamp(pb * 3), 'center')
        label(c, self.lb, 1340, 620, AMBER, clamp(pb * 3), 'center', 24)
        lines, sz = fit_wrap(self.caption, 1300, 1, 46, 'bold', 30)
        text(c, lines[0], CX, 250, sz, 'bold', WHITE, a, 'center')
        self.note(c, t, 740)


# ---------------------------------------------------------------- pictogram grid
class Pictogram(Visual):
    kind = 'pictogram'

    def setup(self):
        sp = self.spec
        if sp.get('segments'):
            self.segs = [(float(s['value']), s.get('label', ''), col_of(s.get('color'), [AMBER, TEAL, GRAY][i % 3]))
                         for i, s in enumerate(sp['segments'])]
            self.caption = sp.get('caption', '')
        else:
            for it in self.items:
                ns = [n for n in find_numbers(it) if n['unit'] == '%' and 0 < n['value'] <= 100]
                if ns:
                    src, n = it, ns[0]; break
            self.segs = [(n['value'], strip_num(src, n) or next((i for i in self.items if i != src), ''), AMBER)]
            self.caption = ''

    def draw(self, c, t):
        gx = 200 if not self.mirror else 1080
        tx = 1040 if not self.mirror else 170
        gy, step = 190, 62
        fill_p = prog(t, .8, 2.2)
        total = sum(s[0] for s in self.segs)
        bounds, acc = [], 0
        for v, lab, col in self.segs:
            bounds.append((acc, acc + round(v), col)); acc += round(v)
        for i in range(100):
            r, cc = divmod(i, 10)
            x, y = gx + cc * step, gy + r * step
            ap = ease_back(prog(t, .02 * (r + cc) * .5, .4))
            if ap <= 0.01:
                continue
            cl = DIM
            for b0, b1, col in bounds:
                if b0 <= i < b1 and i / max(total, 1) <= fill_p:
                    cl = col
            c.save(); c.translate(x + 20, y + 20); c.scale(ap, ap)
            circle(c, 0, -10, 8, cl, 1)
            bp = skia.Path(); bp.moveTo(-14, 22); bp.cubicTo(-14, -2, 14, -2, 14, 22); bp.close()
            c.drawPath(bp, paint(cl, 1))
            c.restore()
        n = len(self.segs)
        if n == 1:
            v, lab, col = self.segs[0]
            a = ease_out(prog(t, .5, .6))
            text(c, fmt_num(v, mknum(v, '%'), ease_out(fill_p)), tx, 420, 170, 'display', col, a)
            lines, sz = fit_wrap(lab, 640, 4, 50, 'bold', 32)
            for i, ln in enumerate(lines):
                text(c, ln, tx, 510 + i * sz * 1.2, sz, 'bold', WHITE, ease_out(prog(t, .9, .6)))
            text(c, 'each figure = 1%', tx, 510 + len(lines) * sz * 1.2 + 40, 24, 'medium', MUTED, ease_out(prog(t, 1.2, .6)))
        else:
            y = 470 - n * 75 + 60
            acc = 0
            for k, (v, lab, col) in enumerate(self.segs):
                st = .8 + 2.2 * acc / max(total, 1)
                acc += v
                a = ease_out(prog(t, st, .5))
                text(c, fmt_num(v, mknum(v, '%'), 1), tx + 40 * (1 - a), y + k * 150, 96, 'display', col, a)
                ls, sz = fit_wrap(lab, 400, 2, 34, 'semibold', 26)
                for j, ln in enumerate(ls):
                    text(c, ln, tx + 300, y - 40 + k * 150 + j * sz * 1.2 + (16 if len(ls) == 1 else 0), sz, 'semibold', WHITE, a)
            if self.caption:
                chip(c, self.caption, tx + 10, y + n * 150 - 60, MUTED, ease_out(prog(t, 3.0, .5)), 'left')


# ---------------------------------------------------------------- bar chart (signed, grouped)
class Bars(Visual):
    kind = 'bars'

    def setup(self):
        sp = self.spec
        self.title = sp.get('title')
        self.groups = []
        if sp.get('groups'):
            for g in sp['groups']:
                self.groups.append(dict(label=g.get('label', ''), bars=[self._bar(b, i) for i, b in enumerate(g['bars'])]))
        elif sp.get('bars'):
            self.groups = [dict(label='', bars=[self._bar(b, i)]) for i, b in enumerate(sp['bars'])]
            self.single = True
        else:
            rows = []
            for it in self.items:
                for part in re.split(r'\s+(?:vs\.?|versus)\s+|\s/\s', it, flags=re.I):
                    ns = find_numbers(part)
                    if ns:
                        rows.append(dict(label=strip_num(part, ns[0]), n=ns[0]))
            for i, r in enumerate(rows[:6]):
                b = dict(label=r['label'] or f'Group {"ABCDEF"[i]}', n=r['n'], color=[AMBER, TEAL, WHITE, GRAY][i % 4],
                         display=None, at=None)
                self.groups.append(dict(label='', bars=[b]))
            if self.title is None:
                self.title = next((i for i in self.items if not find_numbers(i)), '')
        self.single = all(len(g['bars']) == 1 for g in self.groups)
        self.legend = sp.get('legend')
        vals = [b['n']['value'] for g in self.groups for b in g['bars']]
        self.vmax, self.vmin = max(0, max(vals)), min(0, min(vals))
        hl = sp.get('highlight')
        self.hl = hl if isinstance(hl, dict) else ({'index': hl} if hl is not None else None)

    def _bar(self, b, i):
        n = mknum(b['value'], b.get('unit', self.spec.get('unit', '')), sign=b.get('sign', self.spec.get('sign', '')),
                  decimals=b.get('decimals', self.spec.get('decimals')))
        return dict(label=b.get('label', ''), n=n, color=col_of(b.get('color'), [AMBER, TEAL, GRAY][i % 3]),
                    display=b.get('display'), at=b.get('at'), delay=b.get('delay', 0))

    def draw(self, c, t):
        a0 = ease_out(prog(t, 0, .5))
        sp = self.spec
        if self.title:
            ls, sz = fit_wrap(self.title, 1400, 1, 46, 'bold', 30)
            text(c, ls[0], CX, 205, sz, 'bold', WHITE, a0, 'center')
        top, bot = 365, (720 if self.vmin >= 0 else 650)
        rng = (self.vmax - self.vmin) or 1
        # leave headroom for labels
        scale = (bot - top) / rng
        zero = top + self.vmax * scale
        ng = len(self.groups)
        nb = max(len(g['bars']) for g in self.groups)
        bw = 180 if self.single else min(130, 600 / nb)
        inner = 24
        gw = bw * nb + inner * (nb - 1)
        span = 1300
        gap = (span - ng * gw) / max(ng - 1, 1) if ng > 1 else 0
        gap = min(gap, 260 if self.single else 200)
        total = ng * gw + (ng - 1) * gap
        x0 = CX - total / 2
        if sp.get('ylabel'):
            text(c, sp['ylabel'], x0 - 40, top - 30, 22, 'semibold', MUTED, a0)
        line(c, x0 - 60, zero, x0 + total + 60, zero, MUTED, .7, 3, ease_out(prog(t, 0, .6)))
        neg_ext = abs(self.vmin) * scale
        label_y = max(bot, zero + neg_ext + (70 if self.vmin < 0 else 0)) + 48
        k = 0
        hl = self.hl
        hl_on = ease_out(prog(t, self.beat(hl.get('at'), .8), .5)) if hl else 0
        for gi, g in enumerate(self.groups):
            gx = x0 + gi * (gw + gap)
            for bi, b in enumerate(g['bars']):
                if b['at'] == 'hide':
                    k += 1
                    continue
                if b['at'] == 'static' or sp.get('static'):
                    st, p = -1, 1.0
                    pa = a0
                elif b['at'] is not None:
                    st = self.beat(b['at'], .3) + .15 + b.get('delay', 0)
                    p = ease_out(prog(t, st, 1.0)); pa = ease_out(prog(t, st, .3))
                else:
                    st = .3 + k * .35
                    p = ease_out(prog(t, st, 1.0)); pa = ease_out(prog(t, st, .3))
                k += 1
                if pa <= .01:
                    continue
                idx = gi if not self.single else gi
                dim = 1.0
                if hl:
                    target = hl.get('group', hl.get('index'))
                    dim = 1 - .6 * hl_on if idx != target else 1.0
                x = gx + bi * (bw + inner)
                v = b['n']['value']
                h = abs(v) * scale * p
                if abs(v) * scale < 6:
                    h = 6 * pa
                col = b['color']
                yb = zero - h if v >= 0 else zero
                rrect(c, x, yb, bw, h, min(12, bw / 6), col, .95 * pa * dim)
                if hl and idx == hl.get('group', hl.get('index')) and hl_on > 0:
                    rrect(c, x - 8, yb - 8, bw + 16, h + 16, 16, col, .8 * hl_on, 3)
                disp = b['display'] if b['display'] is not None else fmt_num(v, b['n'], p)
                vs = 56 if self.single else 40
                vy = (yb - 20) if v >= 0 else (zero + h + vs * .9 + 6)
                if v == 0 and b['display'] and len(b['display']) > 3:
                    text(c, disp.upper(), x + bw / 2, zero - 22, 22, 'bold', MUTED, pa * dim, 'center', 3)
                else:
                    text(c, disp, x + bw / 2, vy, vs, 'display', col if col != GRAY else WHITE, pa * dim, 'center')
                if self.single:
                    ls, sz = fit_wrap(b['label'], bw + gap * .9, 2, 30, 'semibold', 22)
                    for j, ln in enumerate(ls):
                        text(c, ln, x + bw / 2, label_y + j * sz * 1.2, sz, 'semibold', WHITE, pa * dim, 'center')
            if not self.single and g['label']:
                ga = ease_out(prog(t, .1 + gi * .1, .5))
                text(c, g['label'], gx + gw / 2, bot + 56, 30, 'semibold', WHITE, ga, 'center')
        if self.legend:
            ly = 262
            widths = [measure(L['label'], 24, 'semibold') + 34 for L in self.legend]
            xx = CX - (sum(widths) + 36 * (len(widths) - 1)) / 2
            for L, w in zip(self.legend, widths):
                rrect(c, xx, ly - 20, 22, 22, 5, col_of(L.get('color')), a0)
                text(c, L['label'], xx + 34, ly, 24, 'semibold', MUTED, a0)
                xx += w + 36
        self.note(c, t, sp.get('note_y', 822 if (self.legend or self.vmin < 0) else 258), sp.get('note_x', CX))


# ---------------------------------------------------------------- dials (two or three rings)
class Dials(Visual):
    kind = 'dials'

    def setup(self):
        sp = self.spec
        if sp.get('dials'):
            self.d = [(mknum(d['value'], d.get('unit', '%')), d.get('label', ''), col_of(d.get('color'), [AMBER, GRAY, TEAL][i % 3]), d.get('at'))
                      for i, d in enumerate(sp['dials'])]
        else:
            ns = [n for it in self.items for n in find_numbers(it)]
            self.d = [(n, '', [AMBER, GRAY, TEAL][i % 3], None) for i, n in enumerate(ns[:3])]
        self.bracket = sp.get('bracket')

    def draw(self, c, t):
        n = len(self.d)
        xs = [CX + (i - (n - 1) / 2) * 640 for i in range(n)]
        cy, R = 470, 185
        for i, ((num, lab, col, at), x) in enumerate(zip(self.d, xs)):
            st = self.beat(at, .3 + i * .6) if at is not None else .3 + i * .6
            p = ease_out(prog(t, st, 1.4)); a = ease_out(prog(t, st - .2, .5))
            arc(c, x, cy, R, 135, 270, DIM, .6 * a, 22)
            arc(c, x, cy, R, 135, 270 * num['value'] / 100 * p, col, a, 22)
            for k in range(11):
                aa = math.radians(135 + 27 * k)
                line(c, x + (R - 34) * math.cos(aa), cy + (R - 34) * math.sin(aa), x + (R - 46) * math.cos(aa), cy + (R - 46) * math.sin(aa), MUTED, .5 * a, 3)
            text(c, fmt_num(num['value'], num, p), x, cy + 30, 92, 'display', WHITE, a, 'center')
            ls, sz = fit_wrap(lab, 520, 2, 36, 'bold', 26)
            for j, ln in enumerate(ls):
                text(c, ln, x, cy + R + 60 + j * sz * 1.2, sz, 'bold', col if col != GRAY else WHITE, a, 'center')
        if self.bracket and n >= 2:
            bp = ease_in_out(prog(t, self.beat(self.spec.get('bracket_at', 2), 2.5), .7))
            if bp > 0:
                y = cy - R - 40
                pth = skia.Path(); pth.moveTo(xs[0], y + 20); pth.lineTo(xs[0], y); pth.lineTo(xs[1], y); pth.lineTo(xs[1], y + 20)
                draw_path(c, pth, AMBER, 1, 5, bp)
                chip(c, self.bracket, CX, y, AMBER, ease_out(prog(bp, .6, .4)), size=28)
        self.note(c, t, 790)


# ---------------------------------------------------------------- dot crowd (count, then split into groups)
class Dots(Visual):
    kind = 'dots'

    def setup(self):
        sp = self.spec
        self.count = int(sp.get('count', 1000))
        self.number = sp.get('number', '')
        self.caption = sp.get('caption', '')
        self.groups = [dict(label=g.get('label', ''), color=col_of(g.get('color'), [GRAY, AMBER, TEAL][i % 3]), icon=g.get('icon'),
                            share=float(g.get('share', 1))) for i, g in enumerate(sp.get('groups', []))]
        self.split_t = max(self.beat(sp.get('split_at'), 1.5), 1.4) if self.groups else 1e9
        self.start_split = bool(sp.get('start_split'))
        rng = random.Random(11 + self.index)
        cols = 50
        rows = math.ceil(self.count / cols)
        sp_ = 18
        w, h = cols * sp_, rows * sp_
        self.grid = [(CX - w / 2 + (i % cols) * sp_ + sp_ / 2, 520 - h / 2 + (i // cols) * sp_) for i in range(self.count)]
        self.order = list(range(self.count)); rng.shuffle(self.order)
        self.target, self.gidx = [None] * self.count, [0] * self.count
        if self.groups:
            ng = len(self.groups)
            tot = sum(g['share'] for g in self.groups)
            counts = [int(round(self.count * g['share'] / tot)) for g in self.groups]
            counts[-1] = self.count - sum(counts[:-1])
            colw = 1500 / ng
            k = 0
            for gi, cnt in enumerate(counts):
                gc = max(8, int(math.sqrt(cnt * 1.6)))
                gc = min(gc, int((colw - 80) / 15))
                grows = math.ceil(cnt / gc)
                gx0 = 210 + gi * colw + colw / 2 - gc * 15 / 2
                gy0 = 540 - grows * 15 / 2
                self.groups[gi]['cx'] = 210 + gi * colw + colw / 2
                self.groups[gi]['top'] = gy0
                self.groups[gi]['bot'] = gy0 + grows * 15
                for j in range(cnt):
                    i = self.order[k]; k += 1
                    self.target[i] = (gx0 + (j % gc) * 15 + 7, gy0 + (j // gc) * 15)
                    self.gidx[i] = gi
        self.delay = [rng.random() * .6 for _ in range(self.count)]

    def draw(self, c, t):
        appear = prog(t, 0, 1.4)
        sp_t = self.split_t if not self.start_split else -10
        buckets = {}
        for i in range(self.count):
            ap = clamp(appear * 1.6 - self.order[i] / self.count * .6 * 1.6)
            if ap <= 0:
                continue
            x, y = self.grid[i]
            colr = MUTED
            if self.groups:
                m = ease_in_out(prog(t, sp_t + self.delay[i], 1.2))
                if m > 0:
                    tx, ty = self.target[i]
                    x, y = lerp(x, tx, m), lerp(y, ty, m) - math.sin(m * math.pi) * 60
                    colr = self.groups[self.gidx[i]]['color'] if m > .3 else MUTED
            buckets.setdefault((colr, round(ap, 1)), []).append(skia.Point(x, y))
        for (colr, ap), pts in buckets.items():
            p = paint(colr, .9 * ap, stroke=10)
            c.drawPoints(skia.Canvas.kPoints_PointMode, pts, p)
        a = ease_out(prog(t, .2, .6))
        out = ease_out(prog(t, sp_t - .1, .5)) if self.groups else 0
        if self.number:
            text(c, self.number, CX, 300 - 30 * out, 110, 'display', AMBER, a * (1 - out), 'center')
        if self.caption:
            text(c, self.caption, CX, 790, 38, 'semibold', WHITE, ease_out(prog(t, .6, .6)) * (1 - out), 'center')
        for gi, g in enumerate(self.groups):
            ga = ease_out(prog(t, sp_t + .8 + gi * .25, .6))
            if ga <= 0:
                continue
            if g['icon']:
                draw_icon(c, g['icon'], g['cx'], g['top'] - 90, 110, prog(t, sp_t + .8 + gi * .25, 1.0), t, WHITE, g['color'])
            ls, sz = fit_wrap(g['label'], 440, 2, 38, 'bold', 28)
            for j, ln in enumerate(ls):
                text(c, ln, g['cx'], g['bot'] + 60 + j * sz * 1.2, sz, 'bold', g['color'] if g['color'] != GRAY else WHITE, ga, 'center')
        if self.groups and self.spec.get('group_caption'):
            text(c, self.spec['group_caption'], CX, 220, 34, 'semibold', MUTED, ease_out(prog(t, sp_t + 1.2, .6)), 'center')


# ---------------------------------------------------------------- classroom
class Classroom(Visual):
    kind = 'classroom'

    def setup(self):
        sp = self.spec
        self.n = mknum(sp.get('value', 48), sp.get('unit', '%'), sign=sp.get('sign', '+'))
        self.caption = sp.get('caption', '')
        self.rows, self.cols = 4, 6

    def draw(self, c, t):
        x0, y0, dx, dy = 200, 260, 150, 140
        for r in range(self.rows):
            for k in range(self.cols):
                i = r * self.cols + k
                x, y = x0 + k * dx, y0 + r * dy
                a = ease_out(prog(t, .05 * i * .5, .5))
                if a <= 0:
                    continue
                circle(c, x, y, 18, WHITE if (i % 5) else TEAL, .9 * a)
                bp = skia.Path(); bp.moveTo(x - 28, y + 52); bp.cubicTo(x - 28, y + 18, x + 28, y + 18, x + 28, y + 52); bp.close()
                c.drawPath(bp, paint(WHITE if (i % 5) else TEAL, .9 * a))
                rrect(c, x - 52, y + 48, 104, 14, 5, DIM, a)
                bub = ease_back(prog(t, .6 + ((i * 7) % 24) * .06, .4))
                if bub > 0:
                    c.save(); c.translate(x + 34, y - 34); c.scale(bub, bub)
                    rrect(c, -22, -16, 44, 30, 10, AMBER, .95)
                    tri = skia.Path(); tri.moveTo(-12, 12); tri.lineTo(-18, 24); tri.lineTo(-2, 13); tri.close()
                    c.drawPath(tri, paint(AMBER, .95))
                    for d in range(3):
                        circle(c, -10 + d * 10, -1 + 2 * math.sin(t * 6 + d + i), 3, NAVY)
                    c.restore()
        # bar + counter
        bx, base, maxh = 1270, 760, 420
        p = ease_out(prog(t, 1.0, 1.8))
        a = ease_out(prog(t, .8, .5))
        line(c, bx - 50, base, bx + 200, base, MUTED, a, 3)
        rrect(c, bx, base - 150, 150, 150, 12, GRAY, .5 * a)
        h = 150 + (maxh - 150) * p
        rrect(c, bx, base - h, 150, h, 12, TEAL, .9 * a * clamp(p * 4))
        arrow(c, bx + 220, base - 80, bx + 220, base - h + 10, TEAL, a, 8, p, 26)
        text(c, fmt_num(self.n['value'], self.n, p), bx + 75, base - h - 30, 96, 'display', TEAL, a, 'center')
        ls, sz = fit_wrap(self.caption, 380, 2, 32, 'semibold', 24)
        for j, ln in enumerate(ls):
            text(c, ln, bx + 75, base + 48 + j * sz * 1.2, sz, 'semibold', WHITE, a, 'center')
        # second beat: bubbles fade / "AI removed" chip
        self.note(c, t, 200, 560)


# ---------------------------------------------------------------- source card
class Source(Visual):
    kind = 'source'

    def setup(self):
        sp = self.spec
        self.cite = sp.get('cite', self.items[0] if self.items else '')
        self.details = sp.get('details', [])
        self.badges = sp.get('badges', [])
        self.chips = sp.get('chips', [])
        self.question = sp.get('question')

    def draw(self, c, t):
        a = ease_out(prog(t, 0, .6))
        x0, y0, w, h = 190, 210, 700, 560
        c.save(); c.translate(0, 30 * (1 - a)); c.rotate(-1.5 * a)
        rrect(c, x0 + 14, y0 + 14, w, h, 18, '#000000', .25 * a)
        rrect(c, x0, y0, w, h, 18, '#EEF0F4', a)
        rrect(c, x0, y0, w, 14, 7, AMBER, a)
        label(c, 'Source', x0 + 50, y0 + 70, '#5A6275', a, size=22)
        ls, sz = fit_wrap(self.cite, w - 100, 3, 50, 'serif', 34)
        y = y0 + 140
        for ln in ls:
            text(c, ln, x0 + 50, y, sz, 'serif', '#141A28', a); y += sz * 1.25
        y += 10
        for d in self.details:
            dl, ds = fit_wrap(d, w - 100, 2, 28, 'medium', 22)
            for ln in dl:
                text(c, ln, x0 + 50, y, ds, 'medium', '#4A5266', a); y += ds * 1.35
            y += 6
        for k in range(4):
            yy = y + 20 + k * 30
            if yy < y0 + h - 40:
                rrect(c, x0 + 50, yy, [560, 520, 590, 380][k], 12, 6, '#C9CED8', a * ease_out(prog(t, .4 + k * .1, .4)))
        c.restore()
        # right column
        rx = 1010
        y = 270
        for i, b in enumerate(self.badges):
            st = self.beat(b.get('at'), .6 + i * .8) + .2
            p = ease_back(prog(t, st, .5))
            if p > .01:
                col = col_of(b.get('color'), TEAL)
                txt = b['text'].upper()
                bw = min(760, measure(txt, 32, 'black', 2) + 70)
                c.save(); c.translate(rx + bw / 2, y); c.scale(p, p)
                rrect(c, -bw / 2, -40, bw, 80, 14, NAVY, .9)
                rrect(c, -bw / 2, -40, bw, 80, 14, col, clamp(p), 5)
                text(c, txt, 0, 12, 32, 'black', col, clamp(p), 'center', 2)
                c.restore()
                if b.get('struck'):
                    sp2 = ease_in_out(prog(t, self.beat(b['struck'], st + 1), .4))
                    line(c, rx - 10, y, rx - 10 + (bw + 20) * sp2, y, RED, 1, 6)
            if i < len(self.badges) - 1:
                st2 = self.beat(self.badges[i + 1].get('at'), .6 + (i + 1) * .8)
                arrow(c, rx + 50, y + 50, rx + 50, y + 110, MUTED, 1, 5, ease_out(prog(t, st2 - .3, .5)), 16)
            y += 160
        if self.chips:
            st = self.beat(self.spec.get('chips_at'), 2.0)
            xx = rx
            y -= 20
            for i, s in enumerate(self.chips):
                p = ease_back(prog(t, st + i * .35, .45))
                w = measure(s, 24, 'semibold') + 44
                if xx + w > 1820:
                    xx = rx; y += 66
                if p > .01:
                    c.save(); c.translate(xx + w / 2, y); c.scale(p, p)
                    chip(c, s, 0, 0, AMBER, clamp(p))
                    c.restore()
                xx += w + 16
            y += 110
        if self.question:
            q = self.question
            st = self.beat(q.get('at'), 3.0)
            p = ease_out(prog(t, st, .6))
            if p > .01:
                y = max(y, 600)
                draw_icon(c, q.get('icon', 'clock'), rx + 50, y, 100, prog(t, st, 1.0), t, WHITE, AMBER)
                ls, sz = fit_wrap(q['text'], 640, 2, 42, 'bold', 30)
                for j, ln in enumerate(ls):
                    text(c, ln, rx + 130, y + 14 - (len(ls) - 1) * sz * .6 + j * sz * 1.2, sz, 'bold', WHITE, p)


# ---------------------------------------------------------------- hub (center + satellites)
class Hub(Visual):
    kind = 'hub'

    def setup(self):
        sp = self.spec
        self.center = sp.get('center', 'flask')
        self.nodes = sp.get('nodes', self.items[:4])
        self.node_icon = sp.get('node_icon', 'building')
        self.title = sp.get('title', '')
        self.caption = sp.get('caption', '')

    def draw(self, c, t):
        cx, cy = CX, 500
        n = len(self.nodes)
        pos = []
        for i in range(n):
            ang = math.radians(-150 + i * (300 / max(n - 1, 1))) if n > 2 else math.radians(180 * i)
            # spread on an ellipse, left/right sides
            side = -1 if i < n / 2 else 1
            k = i if side < 0 else i - n // 2
            m = n // 2 if side < 0 else n - n // 2
            yy = cy + (k - (m - 1) / 2) * 300
            pos.append((cx + side * 560, yy))
        a = ease_out(prog(t, 0, .5))
        if self.title:
            text(c, self.title, cx, 200, 46, 'bold', WHITE, a, 'center')
        for i, (x, y) in enumerate(pos):
            st = self.beat(self.spec.get('nodes_at'), .3) + i * .25
            lp = ease_in_out(prog(t, st + .3, .8))
            pth = skia.Path(); pth.moveTo(x - math.copysign(110, x - cx), y)
            pth.cubicTo((x + cx) / 2, y, (x + cx) / 2, cy, cx - math.copysign(130, x - cx), cy)
            draw_path(c, pth, TEAL, .6, 4, lp)
            if lp >= 1:  # traveling pulse
                m = skia.PathMeasure(pth, False)
                L = m.getLength()
                ph = ((t * .5 + i * .27) % 1)
                pt, _ = m.getPosTan(L * ph)
                circle(c, pt.x(), pt.y(), 7, AMBER, math.sin(ph * math.pi))
            na = ease_back(prog(t, st, .5))
            if na > .01:
                c.save(); c.translate(x, y); c.scale(na, na)
                rrect(c, -110, -80, 220, 160, 26, PANEL, .95)
                rrect(c, -110, -80, 220, 160, 26, DIM, 1, 3)
                draw_icon(c, self.node_icon, 0, -14, 90, 1, t, WHITE, AMBER)
                text(c, self.nodes[i], 0, 60, 30, 'bold', WHITE, 1, 'center')
                c.restore()
        cp = ease_back(prog(t, .1, .6))
        glow(c, cx, cy, 260, AMBER, .18 * cp)
        circle(c, cx, cy, 130 * cp, PANEL, 1)
        circle(c, cx, cy, 130 * cp, AMBER, 1, 5)
        draw_icon(c, self.center, cx, cy, 170, prog(t, .3, 1.2), t, WHITE, AMBER)
        if self.caption:
            text(c, self.caption, cx, 760, 34, 'semibold', MUTED, ease_out(prog(t, self.beat(self.spec.get('caption_at'), 1.5), .6)), 'center')


# ---------------------------------------------------------------- brain networks
class Networks(Visual):
    kind = 'networks'

    def setup(self):
        sp = self.spec
        self.heads = sp.get('heads', [{'label': i} for i in self.items[:3]])
        rng = random.Random(5)
        pts = []
        while len(pts) < 34:
            x, y = rng.uniform(-1, 1), rng.uniform(-1, 1)
            if x * x + y * y < .8:
                pts.append((x * 120, y * 110 - 10))
        edges = []
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = math.dist(pts[i], pts[j])
                if d < 95:
                    edges.append((d, i, j, rng.random()))
        edges.sort(key=lambda e: e[3])
        self.pts, self.edges = pts, edges

    def head(self, c, x, y, a):
        p = skia.Path()
        p.moveTo(x - 150, y + 40)
        p.cubicTo(x - 175, y - 130, x - 40, y - 200, x + 40, y - 180)
        p.cubicTo(x + 140, y - 160, x + 175, y - 70, x + 160, y - 10)
        p.lineTo(x + 190, y + 40); p.lineTo(x + 160, y + 52)
        p.cubicTo(x + 165, y + 90, x + 150, y + 110, x + 100, y + 110)
        p.lineTo(x + 90, y + 170); p.lineTo(x - 100, y + 170)
        p.cubicTo(x - 100, y + 120, x - 140, y + 90, x - 150, y + 40)
        c.drawPath(p, paint(PANEL, .9 * a))
        c.drawPath(p, paint(MUTED, .8 * a, 4))

    def draw(self, c, t):
        n = len(self.heads)
        for hi, hd in enumerate(self.heads):
            x = CX + (hi - (n - 1) / 2) * 540
            y = 440
            st = (self.beat(hd.get('at'), .2) if hd.get('at') is not None else .2) + hi * .4
            a = ease_out(prog(t, st, .6))
            if a <= .01:
                continue
            self.head(c, x, y, a)
            dens = float(hd.get('density', 1 - hi * .4))
            col = col_of(hd.get('color'), [TEAL, WHITE, AMBER][hi % 3])
            ne = int(len(self.edges) * dens)
            grow = ease_out(prog(t, st + .3, 1.6))
            for k, (d, i, j, r) in enumerate(self.edges[:ne]):
                if k / max(ne, 1) > grow:
                    break
                fl = .35 + .35 * (0.5 + 0.5 * math.sin(t * 3 + r * 20))
                (x1, y1), (x2, y2) = self.pts[i], self.pts[j]
                c.drawLine(x + x1, y + y1, x + x2, y + y2, paint(col, fl * a, 2.5))
            used = set()
            for (d, i, j, r) in self.edges[:ne]:
                used.add(i); used.add(j)
            for i, (px, py) in enumerate(self.pts):
                circle(c, x + px, y + py, 5 if i in used else 3, col if i in used else DIM, a)
            text(c, hd.get('label', ''), x, y + 250, 40, 'bold', WHITE, a, 'center')
            if hd.get('tag'):
                chip(c, hd['tag'], x, y + 310, col, ease_out(prog(t, self.beat(hd.get('tag_at'), st + 1), .5)))


# ---------------------------------------------------------------- chat window
class Chat(Visual):
    kind = 'chat'

    def setup(self):
        sp = self.spec
        self.title = sp.get('title', self.items[0] if self.items else '')
        self.prompt = sp.get('prompt', '')
        self.reply = sp.get('reply', '')
        self.reply_icon = sp.get('reply_icon', 'lightbulb')

    def draw(self, c, t):
        a = ease_out(prog(t, 0, .5))
        if self.title:
            text(c, self.title, CX, 200, 48, 'extrabold', WHITE, a, 'center')
        x0, y0, w, h = 410, 250, 1100, 560
        p = ease_out(prog(t, .1, .6))
        c.save(); c.translate(0, 40 * (1 - p))
        rrect(c, x0, y0, w, h, 26, PANEL, .95 * p)
        rrect(c, x0, y0, w, h, 26, DIM, p, 3)
        rrect(c, x0, y0, w, 62, 26, '#1C2C4E', p)
        for k, cc in enumerate((RED, AMBER, TEAL)):
            circle(c, x0 + 36 + k * 28, y0 + 31, 8, cc, p * .9)
        text(c, 'AI assistant', x0 + w / 2, y0 + 40, 24, 'semibold', MUTED, p, 'center')
        # typed prompt
        st = self.beat(self.spec.get('prompt_at', 1), .6)
        tp = prog(t, st, max(1.0, len(self.prompt) / 28))
        shown = self.prompt[:int(len(self.prompt) * tp)]
        if tp > 0:
            ls, sz = fit_wrap(self.prompt, 700, 3, 34, 'medium', 28)
            bw = max(measure(l, sz, 'medium') for l in ls) + 60
            bh = len(ls) * sz * 1.35 + 40
            bx, by = x0 + w - 40 - bw, y0 + 110
            rrect(c, bx, by, bw, bh, 22, TEAL, .9)
            k = 0
            for j, ln in enumerate(ls):
                part = shown[k:k + len(ln)] if k < len(shown) else ''
                k += len(ln) + 1
                text(c, part, bx + 30, by + 20 + sz + j * sz * 1.35, sz, 'medium', NAVY, 1)
            ry = by + bh + 40
            rp = ease_back(prog(t, st + max(1.0, len(self.prompt) / 28) + .4, .5))
            if rp > .01:
                c.save(); c.translate(x0 + 40, ry); c.scale(rp, rp)
                rw = 160 + (measure(self.reply, 30, 'semibold') + 40 if self.reply else 0)
                rrect(c, 0, 0, rw, 140, 22, '#22355C', 1)
                draw_icon(c, self.reply_icon, 80, 70, 110, prog(t, st + 1.5, 1), t, WHITE, AMBER)
                if self.reply:
                    text(c, self.reply, 160, 82, 30, 'semibold', WHITE, 1)
                c.restore()
        c.restore()


# ---------------------------------------------------------------- split A vs B
class Split(Visual):
    kind = 'split'

    def setup(self):
        sp = self.spec
        if sp.get('A'):
            self.A, self.B = sp['A'], sp['B']
        else:
            A = B = None
            for it in self.items:
                parts = re.split(r'\s+(?:vs\.?|versus|→|->|or)\s+', it, flags=re.I)
                if len(parts) >= 2:
                    A, B = parts[0], parts[1]; break
            if A is None:
                A = self.items[0] if self.items else 'Before'
                B = self.items[1] if len(self.items) > 1 else 'After'
            self.A, self.B = {'title': A.strip()}, {'title': B.strip().rstrip('?')}
        self.iA = self.A.get('icon') or pick_icon(self.A['title'])
        self.iB = self.B.get('icon') or pick_icon(self.B['title'], avoid=(self.iA,))
        self.sep = sp.get('sep', 'arrow' if '→' in ' '.join(self.items) else 'vs')

    def panel(self, c, x, d, icon, col, t0, t):
        p = ease_out(prog(t, t0, .7))
        if p <= .01:
            return
        y = 200 + 40 * (1 - p)
        rrect(c, x, y, 700, 600, 34, PANEL, .85 * p)
        rrect(c, x, y, 700, 600, 34, col, .9 * p, 4)
        glow(c, x + 350, y + 210, 220, col, .12 * p)
        draw_icon(c, icon, x + 350, y + 210, 240, prog(t, t0 + .1, 1.2), t, WHITE, col)
        lines, sz = fit_wrap(d['title'], 600, 2, 54, 'extrabold', 34)
        yy = y + 420
        for i, ln in enumerate(lines):
            text(c, ln, x + 350, yy + i * sz * 1.15, sz, 'extrabold', WHITE, p, 'center')
        if d.get('sub'):
            sl, ss = fit_wrap(d['sub'], 600, 2, 32, 'medium', 24)
            yy += (len(lines) - 1) * sz * 1.15 + 56
            sa = ease_out(prog(t, self.beat(d.get('sub_at'), t0 + .5), .5))
            for i, ln in enumerate(sl):
                text(c, ln, x + 350, yy + i * ss * 1.3, ss, 'medium', col if col != GRAY else MUTED, sa * p, 'center')

    def draw(self, c, t):
        ta = self.beat(self.A.get('at'), .1) if self.A.get('at') is not None else .1
        tb = self.beat(self.B.get('at'), min(self.beat(1, .9), self.dur * .5)) if self.B.get('at') is not None else min(max(self.beat(1, .9), .7) if len(self.beats) > 1 else .9, self.dur * .5)
        self.panel(c, 160, self.A, self.iA, col_of(self.A.get('color'), TEAL), ta, t)
        self.panel(c, 1060, self.B, self.iB, col_of(self.B.get('color'), AMBER), tb, t)
        p = ease_back(prog(t, tb - .2, .6))
        if p > .01:
            circle(c, CX, 500, 58 * p, NAVY, 1)
            circle(c, CX, 500, 58 * p, MUTED, .8, 3)
            if self.sep == 'arrow':
                arrow(c, CX - 26, 500, CX + 26, 500, WHITE, p, 7, p, 18)
            elif self.sep == 'or':
                text(c, 'OR', CX, 516, 40 * p, 'display', WHITE, p, 'center')
            else:
                text(c, 'VS', CX, 516, 44 * p, 'display', WHITE, p, 'center')


# ---------------------------------------------------------------- icon + caption
class IconCaption(Visual):
    kind = 'icon'

    def setup(self):
        sp = self.spec
        self.icon = sp.get('icon') or self.scene.get('icon') or pick_icon(self.desc + ' ' + ' '.join(self.items))
        self.title = sp.get('title', self.items[0] if self.items else '')
        self.subs = sp.get('subs', self.items[1:3])
        self.tag = sp.get('tag')

    def draw(self, c, t):
        if not self.title:
            draw_icon(c, self.icon, CX, 480, 460, prog(t, .1, 1.4), t, WHITE, AMBER)
            return
        ix = 540 if not self.mirror else 1380
        tx = 920 if not self.mirror else 160
        bob = 8 * math.sin(t * 1.4)
        glow(c, ix, 480, 360, TEAL, .16 * ease_out(prog(t, 0, .8)))
        circle(c, ix, 480 + bob, 230, PANEL, .9 * ease_out(prog(t, 0, .6)))
        ring = skia.Path(); ring.addCircle(ix, 480 + bob, 230)
        draw_path(c, ring, TEAL, .7, 4, ease_in_out(prog(t, 0, 1.2)))
        draw_icon(c, self.icon, ix, 480 + bob, 300, prog(t, .25, 1.3), t, WHITE, AMBER)
        a = ease_out(prog(t, .45, .6))
        dx = (50 if not self.mirror else -50) * (1 - a)
        lines, sz = fit_wrap(self.title, 820, 4, 72, 'extrabold', 42)
        sub_l = [fit_wrap(s, 820, 2, 36, 'medium', 26) for s in self.subs]
        total = len(lines) * sz * 1.15 + 40 + sum(len(l) * s * 1.25 + 26 for l, s in sub_l) + (60 if self.tag else 0)
        y = 480 - total / 2 + sz * .8
        if self.tag:
            chip(c, self.tag, tx, y - sz * .8 - 10, AMBER, ease_out(prog(t, .3, .5)), 'left', 22)
            y += 60
        for i, ln in enumerate(lines):
            text(c, ln, tx + dx, y + i * sz * 1.15, sz, 'extrabold', WHITE, a)
        y += (len(lines) - 1) * sz * 1.15 + 40
        line(c, tx, y, tx + 160, y, AMBER, 1, 7, ease_out(prog(t, .8, .5)))
        y += 22
        for k, ((sl, ss), s) in enumerate(zip(sub_l, self.subs)):
            sa = ease_out(prog(t, self.beat(k + 1, 1.2 + k * .5), .6))
            for j, ln in enumerate(sl):
                text(c, ln, tx, y + ss + 18 + j * ss * 1.25, ss, 'medium', MUTED, sa)
            y += len(sl) * ss * 1.25 + 26


# ---------------------------------------------------------------- headline card(s)
class Headline(Visual):
    kind = 'headline'

    def setup(self):
        sp = self.spec
        self.heads = sp.get('heads') or [self.items[0] if self.items else self.desc[:80]]
        self.stamp = sp.get('stamp', self.items[1] if len(self.items) > 1 else 'CHECK THE STUDY')
        self.stamp_col = col_of(sp.get('stamp_color'), AMBER)
        self.callout = sp.get('callout')

    def card(self, c, head, k, n, t, fade):
        st = k * .6
        a = ease_out(prog(t, st, .6)) * fade
        if a <= .01:
            return
        off = (k - (n - 1) / 2)
        ang = -2.5 * (1 - ease_out(prog(t, st, .9))) + ((-2.2 if k % 2 == 0 else 1.8) if n > 1 else -1.2)
        c.save()
        c.translate(CX + off * 360 + 200 * (1 - ease_out(prog(t, st, .7))), 470 + off * 250)
        c.rotate(ang)
        cw, ch = (1520, 480) if n == 1 else (1300, 340)
        rrect(c, -cw / 2 + 16, -ch / 2 + 16, cw, ch, 14, '#000000', .25 * a)
        rrect(c, -cw / 2, -ch / 2, cw, ch, 14, '#EEF0F4', a)
        rrect(c, -cw / 2, -ch / 2, cw, 60, 14, '#DADDE4', a)
        text(c, 'THE DAILY CLAIM', -cw / 2 + 40, -ch / 2 + 40, 24, 'serif', '#5A6275', a, tracking=4)
        for q in range(3):
            circle(c, cw / 2 - 40 - q * 28, -ch / 2 + 30, 7, '#9AA1B0', a)
        lines, sz = fit_wrap(head, cw - 140, 2 if n > 1 else 3, 78 if n == 1 else 64, 'serif', 40)
        y0 = -ch / 2 + 110 + sz * .75
        for i, ln in enumerate(lines):
            text(c, ln, -cw / 2 + 60, y0 + i * sz * 1.18, sz, 'serif', '#141A28', a)
        yl = y0 + len(lines) * sz * 1.18 - 10
        for q in range(3):
            if yl + q * 30 < ch / 2 - 30:
                rrect(c, -cw / 2 + 60, yl + q * 30, [cw - 220, cw - 340, cw - 700][q], 12, 6, '#C3C8D2', a)
        hp = ease_in_out(prog(t, st + .8, .8))
        if hp > 0:
            w = measure(lines[0], sz, 'serif')
            rrect(c, -cw / 2 + 56, y0 + 12, (w + 8) * hp, 10, 5, AMBER, .9 * fade)
        c.restore()

    def draw(self, c, t):
        fade = 1.0
        if self.callout:
            cst = self.beat(self.spec.get('callout_at', 2), self.dur * .6)
            fade = 1 - .8 * ease_in_out(prog(t, cst, .6))
        n = len(self.heads)
        for k, h in enumerate(self.heads):
            self.card(c, h, k, n, t, fade)
        sp = prog(t, self.beat(self.spec.get('stamp_at', 1), 1.6), .5)
        if sp > 0 and self.stamp:
            s = 1.6 - .6 * ease_out(sp)
            sx, sy = (1480, 700) if n == 1 else (1450, 730)
            if self.spec.get('stamp_center'):
                sx, sy = CX, 470
            c.save(); c.translate(sx, sy); c.rotate(-10); c.scale(s, s)
            al = ease_out(sp) * fade
            stamp = self.stamp.upper()
            w = measure(stamp, 40, 'black', 3) + 60
            rrect(c, -w / 2, -42, w, 84, 12, NAVY, .85 * al)
            rrect(c, -w / 2, -42, w, 84, 12, self.stamp_col, al, 7)
            text(c, stamp, 0, 14, 40, 'black', self.stamp_col, al, 'center', 3)
            c.restore()
        if self.callout:
            p = ease_out(prog(t, cst + .2, .6))
            if p > .01:
                ls, sz = fit_wrap(self.callout, 1200, 3, 54, 'bold', 34)
                h = len(ls) * sz * 1.3 + 90
                y0 = 480 - h / 2 + 30 * (1 - p)
                rrect(c, 300, y0, 1320, h, 28, PANEL, .95 * p)
                rrect(c, 300, y0, 1320, h, 28, TEAL, p, 4)
                draw_icon(c, 'lightbulb', 400, y0 + h / 2, 110, prog(t, cst + .3, 1), t, WHITE, TEAL, p)
                for i, ln in enumerate(ls):
                    text(c, ln, 490, y0 + 45 + sz + i * sz * 1.3 - 10, sz, 'bold', WHITE, p)


# ---------------------------------------------------------------- quote / callout
class Quote(Visual):
    kind = 'quote'

    def setup(self):
        sp = self.spec
        q = sp.get('text', self.items[0] if self.items else '')
        self.attr = sp.get('attr', '')
        m = re.match(r'^(.*?)\s*[—–-]\s*([^—–-]{2,60})$', q)
        if not self.attr and m and q[:1] in '"“':
            q, self.attr = m.group(1), m.group(2)
        self.q = q.strip().strip('"“”')

    def draw(self, c, t):
        a = ease_out(prog(t, 0, .5))
        words = self.q.split()
        lines, sz = fit_wrap(self.q, 1120, 5, 62, 'semibold', 36)
        lh = sz * 1.3
        h = max(300, 120 + len(lines) * lh + (80 if self.attr else 0) + 40)
        x0, w = 260, 1400
        y0 = 488 - h / 2
        rrect(c, x0, y0, w, h, 30, PANEL, .8 * a)
        rrect(c, x0, y0, 12, h * ease_in_out(prog(t, 0, .8)), 6, AMBER, 1)
        text(c, '“', x0 + 60, y0 + 190, 240, 'display', AMBER, .9 * a)
        rev = max(self.beat(1, self.dur * .5) - .3, 1.0) if len(self.beats) > 1 else min(self.dur * .6, 2.6)
        shown = ease_out(prog(t, .3, rev)) * len(words) + 0.001
        idx = 0
        yy = y0 + 80 + sz
        for ln in lines:
            xx = x0 + 230
            for wd in ln.split():
                wa = clamp(shown - idx)
                text(c, wd, xx, yy + 10 * (1 - wa), sz, 'semibold', WHITE, wa)
                xx += measure(wd + ' ', sz, 'semibold')
                idx += 1
            yy += lh
        if self.attr:
            text(c, '— ' + self.attr, x0 + 230, yy + 30, 30, 'medium', TEAL, ease_out(prog(t, rev, .6)))


# ---------------------------------------------------------------- stat row
class Stats(Visual):
    kind = 'stats'

    def setup(self):
        sp = self.spec
        self.cells = []
        if sp.get('cells'):
            for cl in sp['cells']:
                self.cells.append((mknum(cl['value'], cl.get('unit', ''), cl.get('prefix', '')), cl.get('label', ''), cl.get('icon')))
        else:
            for it in self.items:
                ns = find_numbers(it)
                if ns:
                    self.cells.append((ns[0], strip_num(it, ns[0]) or it, None))
        self.cells = self.cells[:4]
        used = []
        self.icons = []
        for n, lab, ic in self.cells:
            ic = ic or pick_icon(lab, avoid=tuple(used) + ('question',))
            used.append(ic); self.icons.append(ic)
        self.title = sp.get('title', next((i for i in self.items if not find_numbers(i)), ''))

    def draw(self, c, t):
        n = len(self.cells)
        cw, gap = 440, 50
        x0 = CX - (n * cw + (n - 1) * gap) / 2
        top = 250 if self.title else 210
        if self.title:
            text(c, fit_wrap(self.title, 1500, 1, 48, 'bold', 30)[0][0], CX, 200, 48, 'bold', WHITE, ease_out(prog(t, 0, .5)), 'center')
        for i, ((num, lab, _), ic) in enumerate(zip(self.cells, self.icons)):
            st = self.beats[i] if len(self.beats) >= n and self.beats[i] < self.dur - 1.5 else .2 + i * .35
            p = ease_out(prog(t, st, .7))
            if p <= .01:
                continue
            x = x0 + i * (cw + gap)
            y = top + 40 * (1 - p)
            col = AMBER if i % 2 == 0 else TEAL
            rrect(c, x, y, cw, 560, 30, PANEL, .8 * p)
            rrect(c, x, y, cw, 6, 3, col, p)
            draw_icon(c, ic, x + cw / 2, y + 130, 150, prog(t, st + .1, 1.0), t, WHITE, col)
            s = fmt_num(num['value'], num, ease_out(prog(t, st + .2, 1.2)))
            sz = 120 if len(s) <= 4 else 90
            text(c, s, x + cw / 2, y + 330, sz, 'display', col, p, 'center')
            ls, ss = fit_wrap(lab, cw - 60, 3, 34, 'semibold', 24)
            for j, ln in enumerate(ls):
                text(c, ln, x + cw / 2, y + 400 + j * ss * 1.25, ss, 'semibold', WHITE, p, 'center')


# ---------------------------------------------------------------- timeline
class Timeline(Visual):
    kind = 'timeline'

    def setup(self):
        sp = self.spec
        if sp.get('events'):
            self.ev = [(e.get('tag'), e.get('label', ''), e.get('icon')) for e in sp['events']]
        else:
            ev = []
            for it in self.items:
                m = YEAR_RE.search(it)
                key = m.group(0) if m else None
                labl = (it[:m.start()] + it[m.end():]).strip(' :-–—,') if m else it
                ev.append((key, labl, None))
            self.ev = ev[:6]
        self.title = sp.get('title')

    def draw(self, c, t):
        n = len(self.ev)
        y = 490
        x0, x1 = 200, 1720
        if self.title:
            text(c, self.title, CX, 210, 46, 'bold', WHITE, ease_out(prog(t, 0, .5)), 'center')
        lp = ease_in_out(prog(t, .2, max(1.5, min(self.dur * .6, 3.5))))
        line(c, x0, y, x1, y, DIM, 1, 6)
        line(c, x0, y, x1, y, TEAL, 1, 6, lp)
        hl = self.spec.get('highlight', n - 1)
        for i, (tag, lab, ic) in enumerate(self.ev):
            fx = (i + .5) / n
            x = x0 + fx * (x1 - x0)
            ap = ease_back(prog(lp, fx - .05, .15)) if lp < 1 else 1
            ap = min(ap, 1.2)
            if ap <= .01:
                continue
            cl = AMBER if i == hl else TEAL
            circle(c, x, y, 20 * ap, cl)
            circle(c, x, y, 8 * ap, NAVY)
            up = i % 2 == 0
            a = clamp(ap)
            if ic:
                draw_icon(c, ic, x, y + (-110 if up else 110), 110, a, t, WHITE, cl)
            elif tag:
                ts = 60 if len(tag) <= 5 else 44
                text(c, tag, x, y + (-60 if up else 60 + ts * .75), ts, 'display', AMBER if i == hl else WHITE, a, 'center')
            ls, sz = fit_wrap(lab, (x1 - x0) / n * 1.7, 3, 30, 'semibold', 22)
            for j, ln in enumerate(ls):
                yy = (y - 142 - (len(ls) - 1 - j) * sz * 1.2) if up else (y + 160 + j * sz * 1.2)
                if ic:
                    yy += -60 if up else 60
                elif not tag:
                    yy += 50 if up else -50
                text(c, ln, x, yy, sz, 'semibold', MUTED if tag else WHITE, a, 'center')
            line(c, x, y + (-24 if up else 24), x, y + (-40 if up else 40), MUTED, a, 3)
        self.note(c, t, 800)


# ---------------------------------------------------------------- checklist
class Checklist(Visual):
    kind = 'checklist'

    def setup(self):
        sp = self.spec
        if sp.get('rows'):
            self.rows = sp['rows']; self.title = sp.get('title', '')
        else:
            its = list(self.items)
            self.title = ''
            if len(its) >= 3 and (its[0].endswith(':') or len(its) > 5):
                self.title = its.pop(0).rstrip(':')
            self.rows = its[:5]
        self.style = sp.get('style', 'check')
        self.done = sp.get('done')          # rows < done are already complete at t=0
        self.active = sp.get('active')      # row index that completes during this scene
        self.footer = sp.get('footer')
        self.placeholder = sp.get('placeholder', 'Rule {n}')

    def draw(self, c, t):
        n = len(self.rows)
        x0 = 330
        step = min(140, (BOTTOM - 300) / max(n, 1))
        block = n * step + (100 if self.title else 0) + (80 if self.footer else 0)
        y = 480 - block / 2
        if self.title:
            text(c, self.title, x0 - 40, y + 50, 52, 'extrabold', WHITE, ease_out(prog(t, 0, .5)))
            y += 100
        nb = len(self.beats)
        rules = self.done is not None or self.active is not None
        for i, r in enumerate(self.rows):
            if rules:
                if self.done is not None and i < self.done:
                    st, state = -1, 'done'
                elif i == self.active:
                    st, state = self.beat(self.spec.get('active_at', 0), .3) + .2, 'active'
                else:
                    st, state = -1, 'empty'
            else:
                ats = self.spec.get('at')
                at = ats[i] if ats else None
                st = self.beat(at, .3) + .45 * sum(1 for q in ats[:i] if q == at) if at is not None else (self.beats[i] if nb >= n else .3 + i * min(.8, (self.dur * .6) / max(n, 1)))
                state = 'active'
            p = ease_out(prog(t, st, .6)) if state == 'active' else ease_out(prog(t, 0, .5))
            if p <= .01:
                continue
            yy = y + i * step + step / 2
            dx = 40 * (1 - p) if state == 'active' else 0
            hl = state == 'active' and rules
            rrect(c, x0 - 40 + dx, yy - step * .42, 1340, step * .84, 22, PANEL, (.95 if hl else .7) * p)
            if hl:
                rrect(c, x0 - 40 + dx, yy - step * .42, 1340, step * .84, 22, AMBER, p * .9, 3)
            if state == 'empty':
                rrect(c, x0 + 2, yy - 28, 56, 56, 12, DIM, p, 4)
                txt = self.placeholder.format(n=i + 1)
                text(c, txt, x0 + 100, yy + 14, 40, 'semibold', DIM, p)
                continue
            ip = 1 if state == 'done' else prog(t, st + .1, .6)
            if self.style == 'warn':
                draw_icon(c, 'warning', x0 + 30 + dx, yy, 64, ip, t, AMBER, WHITE)
            elif self.style == 'question':
                draw_icon(c, 'question', x0 + 30 + dx, yy, 64, ip, t, TEAL, AMBER)
            elif self.style == 'number':
                circle(c, x0 + 30 + dx, yy, 30, AMBER, p)
                text(c, str(i + 1), x0 + 30 + dx, yy + 13, 36, 'black', NAVY, p, 'center')
            else:
                if rules:
                    rrect(c, x0 + 2 + dx, yy - 28, 56, 56, 12, TEAL, p, 4)
                    ck = skia.Path(); ck.moveTo(x0 + 14 + dx, yy); ck.lineTo(x0 + 26 + dx, yy + 13); ck.lineTo(x0 + 48 + dx, yy - 13)
                    draw_path(c, ck, AMBER, 1, 8, ease_out(ip))
                else:
                    draw_icon(c, 'check', x0 + 30 + dx, yy, 64, ip, t, TEAL, AMBER)
            ls, sz = fit_wrap(r, 1150, 2, 42, 'semibold', 28)
            off = -(len(ls) - 1) * sz * .6
            for j, ln in enumerate(ls):
                text(c, ln, x0 + 100 + dx, yy + sz * .35 + off + j * sz * 1.2, sz, 'semibold', WHITE if state != 'done' or not rules else MUTED, p)
        if self.footer:
            fa = ease_out(prog(t, self.beat(self.spec.get('footer_at', 1), 1.5), .6))
            chip(c, self.footer, CX, y + n * step + 50, AMBER, fa, size=28)


# ---------------------------------------------------------------- end card
class EndCard(Visual):
    kind = 'end'

    def draw(self, c, t):
        a = ease_out(prog(t, 0, .8)) * (1 - prog(t, self.dur - .8, .8))
        draw_icon(c, 'magnifier', CX, 380, 220, prog(t, .1, 1.2), t, WHITE, AMBER, a)
        text(c, 'THE EVIDENCE', CX, 600, 84, 'display', WHITE, a, 'center', 6)
        text(c, 'BEHIND THE HEADLINES', CX, 680, 40, 'bold', AMBER, a, 'center', 9)
        text(c, 'We read the paper so you don’t have to.', CX, 760, 30, 'medium', MUTED, a * ease_out(prog(t, .6, .6)), 'center')


TYPES = {k.kind: k for k in (ChapterCard, BigNumber, Change, Pictogram, Bars, Dials, Dots, Classroom, Source, Hub,
                             Networks, Chat, Split, IconCaption, Headline, Quote, Stats, Timeline, Checklist, EndCard)}

PEOPLE = ('student', 'participant', 'people', 'adult', 'user', 'respondent', 'worker', 'teen', 'of us', 'americans', 'volunteer')
VS_RE = re.compile(r'\s(vs\.?|versus)\s', re.I)


def feasible(kind, items, nums, pct, years):
    if kind == 'bars':
        return len(nums) >= 2
    if kind == 'stats':
        return 2 <= sum(1 for i in items if find_numbers(i)) <= 4
    if kind == 'pictogram':
        return bool(pct)
    if kind == 'big_number':
        return bool(nums)
    if kind == 'change':
        return len(nums) == 2
    if kind == 'timeline':
        return len(items) >= 2
    if kind in ('quote', 'headline'):
        return bool(items)
    if kind == 'checklist':
        return len(items) >= 2
    if kind == 'split':
        return any(VS_RE.search(' ' + i + ' ') for i in items) or len(items) >= 2
    if kind in ('dials', 'dots', 'classroom', 'source', 'hub', 'networks', 'chat', 'line'):
        return False  # need an explicit spec
    return True


def choose_type(scene, items, prev):
    """Pick a visual type: explicit type, then description cues, then the shape of the on-screen data.
    Avoids repeating the previous scene's type where a good alternative exists."""
    if scene.get('type') in TYPES:
        return scene['type']
    d = ' ' + (scene.get('visual') or '').lower() + ' '
    j = ' '.join(items)
    jl = j.lower()
    nums = [n for it in items for n in find_numbers(it)]
    years = YEAR_RE.findall(j)
    pct = [n for n in nums if n['unit'] == '%' and 0 < n['value'] <= 100]
    has_vs = bool(VS_RE.search(' ' + jl + ' '))
    cands = []
    cues = [
        ('quote', ('quote card', 'callout', 'pull-quote', 'says:', 'statement')),
        ('timeline', ('timeline', 'chronolog', 'history of', 'year by year')),
        ('headline', ('headline', 'newspaper', 'news clip', 'article', 'tweet', 'viral post', 'clickbait')),
        ('change', (' rises from ', ' drops from ', ' goes from ', ' from ')),
        ('bars', ('bar chart', 'bar graph', ' bars', 'comparison chart', ' bar ')),
        ('pictogram', ('pictogram', 'grid of', 'icon grid', 'dots representing', 'out of 100', 'pie chart')),
        ('split', ('split screen', 'split-screen', 'side by side', 'side-by-side', ' versus ', ' vs ', 'two panels', 'a vs b')),
        ('checklist', ('checklist', 'list of', 'bullet', 'takeaways', 'steps', 'tips', 'caveat cards', 'sticky notes')),
        ('big_number', ('big number', 'counter', 'counting up', 'large number', 'statistic')),
        ('icon', (' icon', 'illustration', 'symbol', 'animated brain', 'robot', 'character')),
    ]
    for kind, kws in cues:
        if any(k in d for k in kws):
            cands.append(kind)
    if items and items[0][:1] in '"“':
        cands.append('quote')
    if len(set(years)) >= 2:
        cands.append('timeline')
    if len(nums) == 2 and '→' in j:
        cands.append('change')
    if len(nums) >= 2 and (has_vs or len({n['unit'] for n in nums}) == 1 and nums[0]['unit'] in ('%', 'x', '×', '$')):
        cands.append('bars')
    if 2 <= sum(1 for i in items if find_numbers(i)) <= 4:
        cands.append('stats')
    if (has_vs or re.search(r'\sor\s', jl)) and len(nums) < 2:
        cands.append('split')
    if pct and any(k in d + jl for k in PEOPLE):
        cands.append('pictogram')
    if nums:
        cands.append('big_number')
    if len(items) >= 3 and not nums:
        cands.append('checklist')
    if pct:
        cands.append('pictogram')
    cands += ['icon']
    cands = [k for k in dict.fromkeys(cands) if feasible(k, items, nums, pct, years)]
    for k in cands:
        if k != prev or k == 'icon':
            return k
    return cands[0]


def make_visual(kind, scene, items, dur, beats, mirror, index):
    try:
        return TYPES[kind](scene, items, dur, beats, mirror, index)
    except Exception as e:  # robust fallback: never crash a render on odd text
        print(f'  [visual] {kind} failed for scene {scene.get("id")}: {e!r}; falling back to icon')
        sc = dict(scene); sc.pop('spec', None)
        return IconCaption(sc, items, dur, beats, mirror, index)
