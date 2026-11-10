#!/usr/bin/env python3
"""Vertical "random fact" Shorts renderer (1080x1920, 30 fps).

usage: python3 render_short.py <shorts.json> <day_number> <out_dir> [--voice am_fenrir] [--speed 1.15] [--jobs 2]
       python3 render_short.py <shorts.json> --all <out_dir>
Outputs per short: <slug>.mp4, <slug>_en.srt, <slug>_cover.png   (Spanish comes from YouTube auto-translate)
"""
import argparse
import colorsys
import json
import math
import os
import re
import subprocess
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import skia  # noqa: E402
import vgfx as g  # noqa: E402
from vgfx import paint, rgb, rrect, circle, clamp, ease_out, ease_back, prog, measure  # noqa: E402
import svis  # noqa: E402
import saudio  # noqa: E402
import subs  # noqa: E402

W, H, FPS = 1080, 1920, 30
YEL, CYAN, WHITE, BLACK = '#FFD60A', '#22E4FF', '#FFFFFF', '#000000'
SAFE_L, SAFE_R, SAFE_T, SAFE_B = 60, W - 150, 220, H - 380     # usable: x 60..930, y 220..1540
CX = (SAFE_L + SAFE_R) / 2                                      # 495
TEXT_W = SAFE_R - SAFE_L - 20                                   # 850
GAP = 0.08
TAIL = 0.45
MAX_DUR = 58.0
CAP_SIZE, CAP_MIN = 116, 88
CAP_Y = 1395            # caption baseline (single line)
X264 = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-g', '60', '-r', str(FPS),
        '-video_track_timescale', '15360']

CAT_HUE = [('space', 262), ('astro', 262), ('animal', 152), ('nature', 128), ('ocean', 205), ('sea', 205), ('body', 340),
           ('human', 340), ('health', 340), ('history', 28), ('science', 188), ('food', 18), ('earth', 175), ('geo', 175),
           ('tech', 222), ('language', 300), ('psych', 290), ('physics', 230), ('chem', 190)]
MAG = {'thousand': 1e3, 'million': 1e6, 'billion': 1e9, 'trillion': 1e12}
WNUM = {'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
        'twelve': 12, 'twenty': 20, 'thirty': 30, 'fifty': 50, 'hundred': 100, 'thousand': 1000, 'hundreds': 100, 'thousands': 1000,
        'million': 1e6, 'millions': 1e6, 'billion': 1e9, 'billions': 1e9}
STOPW = set('a an the of to in on at by for and or but with from as is was were that which who it its this these those than per'.split())


def norm(w):
    return re.sub(r"[^\w%'.-]", '', w.lower()).strip(".'-")


def hsv(h, s, v):
    r, g_, b = colorsys.hsv_to_rgb((h % 360) / 360, clamp(s), clamp(v))
    return '#%02X%02X%02X' % (int(r * 255), int(g_ * 255), int(b * 255))


# ================================================================ timeline
def find_number(words):
    """-> (word_idx, value, decimals, prefix_suffix(str), unit_label) or None"""
    for i, w in enumerate(words):
        m = re.match(r'^[\$~]?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(%|x)?', w.strip('("\''))
        if not m:
            continue
        s = m.group(1)
        val = float(s.replace(',', ''))
        dec = len(s.split('.')[1]) if '.' in s else 0
        suf = m.group(2) or ''
        unit = []
        j = i + 1
        if j < len(words) and norm(words[j]) in ('percent',):
            suf = '%'; j += 1
        while j < len(words) and len(unit) < 2:
            nw = norm(words[j])
            if not nw or nw in STOPW or not re.match(r'^[a-z][a-z-]*$', nw):
                break
            unit.append(nw)
            if not nw in MAG:
                break
            j += 1
        year = 1000 <= val <= 2100 and ',' not in s and dec == 0 and not suf
        pre = '$' if w.startswith('$') else ''
        return dict(idx=i, val=val, dec=dec, suf=suf, pre=pre, unit=' '.join(unit).upper(), year=year, comma=',' in s or val >= 10000)
    for i, w in enumerate(words):
        v = word_value(norm(w))
        if v is None:
            continue
        j = i + 1
        nxt = word_value(norm(words[j])) if j < len(words) else None
        if (10 <= v <= 20) and nxt is not None and 10 <= nxt <= 99 and norm(words[j]) not in ('hundred', 'thousand'):
            return dict(idx=i, val=float(v * 100 + nxt), dec=0, suf='', pre='', unit='', year=True, comma=False)
        if j < len(words) and norm(words[j]) in ('hundred', 'hundreds'):
            v *= 100; j += 1
        if j < len(words) and norm(words[j]) in ('thousand', 'thousands') and v < 1000:
            v *= 1000; j += 1
        unit = []
        while j < len(words) and len(unit) < 2:
            u = norm(words[j])
            if not u or u in STOPW or not re.match(r'^[a-z][a-z-]*$', u) or len(u) < 3 or word_value(u) is not None:
                break
            unit.append(u)
            if u not in MAG:
                break
            j += 1
        if not unit:
            continue
        return dict(idx=i, val=float(v), dec=0, suf='', pre='', unit=' '.join(unit).upper(), year=False, comma=v >= 1000)
    return None


UNITS = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}


def word_value(w):
    """'sixty-four' -> 64, 'three' -> 3; 'one' and non-numbers -> None."""
    if w in UNITS[2:]:
        return UNITS.index(w)
    if w in TENS:
        return TENS[w]
    if '-' in w:
        a, _, b = w.partition('-')
        if a in TENS and b in UNITS[1:10]:
            return TENS[a] + UNITS.index(b)
    if w in ('hundred', 'thousand'):
        return {'hundred': 100, 'thousand': 1000}[w]
    return None


def strip_emoji(s):
    return re.sub(r'[^\u0000-\u024F\u2010-\u2027\u2030-\u205E]', '', s).strip()


def find_emph(words, emph):
    if not emph:
        return []
    tgt = [norm(x) for x in str(emph).split() if norm(x)]
    nw = [norm(w) for w in words]
    for i in range(len(nw)):
        if nw[i:i + len(tgt)] == tgt:
            return list(range(i, i + len(tgt)))
    for i, w in enumerate(nw):  # loose: prefix / plural
        if tgt and (w.startswith(tgt[0]) or tgt[0].startswith(w)) and len(w) >= 3:
            return [i]
    return []


def word_times(words, a, b):
    wts = []
    for k, w in enumerate(words):
        x = len(re.sub(r'\W', '', w)) + 1.6
        if k < len(words) - 1:
            if w.endswith((',', ';', ':', '—')):
                x += 3
            elif w.endswith(('.', '!', '?')):
                x += 4.5
        wts.append(x)
    tot = sum(wts)
    out, t = [], a
    for x in wts:
        d = (b - a) * x / tot
        out.append((t, t + d)); t += d
    return out


def caption_chunks(words, times, emph_idx):
    chunks, cur = [], []
    for k, w in enumerate(words):
        if cur:
            chars = sum(len(words[j]) for j in cur) + len(cur) + len(w)
            prev = words[cur[-1]]
            if len(cur) >= 3 or chars > 15 or prev.endswith((',', '.', '!', '?', ';', ':', '—')) or \
                    (k in emph_idx and k - 1 not in emph_idx) or (cur[-1] in emph_idx and k not in emph_idx):
                chunks.append(cur); cur = []
        cur.append(k)
    if cur:
        chunks.append(cur)
    # avoid orphan 1-word tail chunk of a tiny word
    return [dict(words=[words[j] for j in ch], idx=ch, start=times[ch[0]][0], wt=[times[j] for j in ch],
                 emph=[j in emph_idx for j in ch]) for ch in chunks]


def build(short, cache, voice, speed):
    lines = [l for l in short.get('lines', []) if (l.get('en') if isinstance(l, dict) else l)]
    lines = [l if isinstance(l, dict) else {'en': l, 'es': ''} for l in lines]
    beats = short.get('beats') or []
    beats = [b if isinstance(b, dict) else {'visual': str(b), 'emphasis_word': ''} for b in beats]
    while len(beats) < len(lines):
        beats.append({'visual': lines[len(beats)]['en'], 'emphasis_word': ''})
    sp = speed
    for attempt in range(4):
        clips = []
        for i, l in enumerate(lines):
            clips.append(saudio.tts(l['en'].strip(), cache, voice, sp))
            print(f'\r  tts {i + 1}/{len(lines)} @ {sp:.2f}', end='', flush=True)
        total = sum(len(x) for x in clips) / saudio.SR + GAP * (len(clips) - 1) + 0.05 + TAIL
        print(f'  -> {total:.1f}s')
        if total <= MAX_DUR - 0.3 or sp >= 1.45:
            break
        sp = min(1.45, sp * total / (MAX_DUR - 1.0))
    T = {'lines': [], 'segs': [], 'chunks': [], 'punch': [], 'cuts': [], 'placements': [], 'speed': sp}
    t = 0.05
    for i, (l, x) in enumerate(zip(lines, clips)):
        d = len(x) / saudio.SR
        words = l['en'].split()
        tm = word_times(words, t, t + d)
        b = beats[i]
        emph = find_emph(words, b.get('emphasis_word') or b.get('emphasis'))
        num = find_number(words)
        if not emph and num:
            emph = [num['idx']]
        T['placements'].append((t, x))
        T['lines'].append(dict(i=i, en=l['en'].strip(), start=t, end=t + d, words=words, times=tm, emph=emph, num=num,
                               visual=b.get('visual', ''), emph_word=' '.join(words[j] for j in emph)))
        T['chunks'] += [dict(ch, line=i) for ch in caption_chunks(words, tm, set(emph))]
        if emph:
            T['punch'].append(tm[emph[0]][0])
        t += d + GAP
    T['total'] = t - GAP + TAIL
    if T['chunks']:
        T['chunks'][0]['start'] = 0.0
    # extend chunk ends
    for k, ch in enumerate(T['chunks']):
        nxt = T['chunks'][k + 1]['start'] if k + 1 < len(T['chunks']) else T['total'] + 1
        ch['end'] = nxt
    make_segments(T, short)
    return T


def make_segments(T, short):
    cat = short.get('category', '')
    prev_vis = None
    layouts_cycle = ['center', 'duo', 'big', 'center', 'big', 'duo']
    lc = 0
    L = T['lines']
    for i, ln in enumerate(L):
        a = 0.0 if i == 0 else ln['start'] - GAP / 2
        b = L[i + 1]['start'] - GAP / 2 if i + 1 < len(L) else T['total'] + 0.01
        starts = [st for st, _ in ln['times']]
        forced = {}
        if ln['num']:
            ts = starts[ln['num']['idx']]
            forced[ts if ts - a >= 0.85 and b - ts >= 0.9 else a] = 'counter'
        if ln['emph'] and not (ln['num'] and ln['emph'][0] == ln['num']['idx']):
            ts = starts[ln['emph'][0]]
            if ts - a >= 0.85 and b - ts >= 0.9 and all(abs(ts - f) > 1.0 for f in forced):
                forced[ts] = 'keyword'
            elif a not in forced and i > 0:
                forced.setdefault(a, 'keyword')
        bounds = sorted(set([a, b] + list(forced)))
        changed = True
        while changed:   # split long intervals at word starts near the middle
            changed = False
            for k in range(len(bounds) - 1):
                if bounds[k + 1] - bounds[k] > 3.0:
                    mid = (bounds[k] + bounds[k + 1]) / 2
                    cand = [s for s in starts if bounds[k] + 1.0 < s < bounds[k + 1] - 1.0]
                    pick = min(cand, key=lambda s: abs(s - mid)) if cand else mid
                    bounds.insert(k + 1, pick); changed = True
                    break
        ranked = svis.choose(ln['visual'], ln['en'], cat)
        scores_now = dict(svis.choose.last_scores)
        vi = 0
        for k in range(len(bounds) - 1):
            s0, s1 = bounds[k], bounds[k + 1]
            kind = forced.get(s0)
            if i == 0:
                layout = 'hook'
            elif kind:
                layout = kind
            else:
                layout = layouts_cycle[lc % len(layouts_cycle)]; lc += 1
            # visual choice: rotate through top candidates, never repeat back-to-back
            scored = [v for v in ranked if scores_now.get(v, 0) > 0][:3]
            pool = scored if len(scored) >= 2 else (scored + [v for v in svis.category_defaults(cat) if v not in scored])[:3]
            opts = [v for v in pool if v != prev_vis] or pool
            vis = opts[vi % len(opts)]; vi += 1
            sec = next((v for v in ranked if v != vis), 'question')
            T['segs'].append(dict(t0=s0, t1=s1, line=i, layout=layout, vis=vis, vis2=sec, seed=len(T['segs']) * 7 + 3))
            prev_vis = vis
            if s0 > 0.01:
                T['cuts'].append(s0)
    for sg in T['segs']:
        if sg['layout'] == 'counter':
            T['punch'].append(sg['t0'] + 0.8)
    T['punch'].sort()


# ================================================================ drawing
class Scene:
    def __init__(self, short, T, day):
        self.s, self.T, self.day = short, T, day
        cat = (short.get('category') or '').lower()
        self.hue = next((h for k, h in CAT_HUE if k in cat), (sum(map(ord, cat)) * 37) % 360)
        self.small = skia.Surface(108, 192)
        self.hook = strip_emoji(short.get('hook') or short.get('title') or T['lines'][0]['en']).upper()
        self.hook_emph = set(norm(w) for w in T['lines'][0]['emph_word'].upper().split())
        self.cat_label = (short.get('category') or 'random fact').upper()

    # ---------------------------------------------------- background
    def bg(self, c, t, seg):
        h = self.hue + ((seg['line'] % 3) - 1) * 16 if seg else self.hue
        sc = self.small.getCanvas()
        sh = skia.GradientShader.MakeLinear([(0, 0), (0, 192)], [rgb(hsv(h, .85, .36)), rgb(hsv(h + 25, .9, .16)), rgb(hsv(h + 40, .9, .07))], [0, .55, 1])
        sc.drawPaint(skia.Paint(Shader=sh))
        for k, (bx, by, r, dh, a) in enumerate([(.2, .25, 90, -30, .55), (.85, .6, 80, 40, .45), (.5, .95, 70, 180, .25)]):
            x = 108 * (bx + .12 * math.sin(t * (.4 + .1 * k) + k)); y = 192 * (by + .06 * math.cos(t * (.33 + .1 * k) + 2 * k))
            rs = skia.GradientShader.MakeRadial((x, y), r, [rgb(hsv(h + dh, .9, .9), a), rgb(hsv(h + dh, .9, .9), 0)])
            sc.drawPaint(skia.Paint(Shader=rs))
        c.drawImageRect(self.small.makeImageSnapshot(), skia.Rect.MakeWH(W, H), skia.SamplingOptions(skia.FilterMode.kLinear))
        # drifting particles (motion every frame)
        for i in range(36):
            r1 = svis._rng(11, i); r2 = svis._rng(23, i)
            x = (r1 * W + 25 * math.sin(t * .7 + i)) % W
            y = H - ((t * (30 + 60 * r2) + r2 * H) % H)
            circle(c, x, y, 2 + 4 * r1, WHITE, .10 + .18 * (0.5 + 0.5 * math.sin(t * 2 + i)))
        # rotating light rays behind the visual area
        c.save(); c.translate(CX, 760); c.rotate(t * 8)
        for k in range(8):
            c.save(); c.rotate(k * 45)
            pth = skia.Path(); pth.moveTo(0, 0); pth.lineTo(-90, -1100); pth.lineTo(90, -1100); pth.close()
            c.drawPath(pth, paint(WHITE, .025))
            c.restore()
        c.restore()

    # ---------------------------------------------------- HUD
    def hud(self, c, t):
        T = self.T
        x0, x1, y = SAFE_L, SAFE_R, 232
        rrect(c, x0, y, x1 - x0, 14, 7, BLACK, .45)
        fr = clamp(t / T['total'])
        if fr > 0:
            sh = skia.GradientShader.MakeLinear([(x0, 0), (x1, 0)], [rgb(YEL), rgb(CYAN)])
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y, max(14, (x1 - x0) * fr), 14), 7, 7), skia.Paint(AntiAlias=True, Shader=sh))
        lab = f'DAY {self.day}  •  {self.cat_label}'
        w = measure(lab, 30, 'black') + 36
        rrect(c, x0, 266, w, 50, 25, BLACK, .5)
        circle(c, x0 + 22, 291, 7, YEL)
        g.text(c, lab, x0 + 38, 302, 30, 'black', WHITE, .95)

    # ---------------------------------------------------- captions
    def captions(self, c, t):
        ch = next((q for q in self.T['chunks'] if q['start'] <= t < q['end']), None)
        if ch is None:
            return
        lt = t - ch['start']
        size = CAP_SIZE
        words = [w.upper() for w in ch['words']]
        sp = measure(' ', size, 'display')
        def width(sz):
            return sum(measure(w, sz, 'display') for w in words) + measure(' ', sz, 'display') * (len(words) - 1)
        while width(size) > TEXT_W and size > CAP_MIN:
            size -= 4
        rows = [list(range(len(words)))]
        if width(size) > TEXT_W and len(words) > 1:
            rows = [list(range(len(words) - 1)), [len(words) - 1]] if len(words) == 2 else [[0, 1], list(range(2, len(words)))]
        sp = measure(' ', size, 'display') + size * 0.14
        pop = 1.0 if ch['start'] <= 0.0 else 0.82 + 0.18 * ease_back(prog(lt, 0, 0.12))
        lh = size * 1.08
        y0 = CAP_Y - (len(rows) - 1) * lh / 2 if len(rows) > 1 else CAP_Y
        c.save(); c.translate(CX, y0 - size * .35); c.scale(pop, pop); c.translate(-CX, -(y0 - size * .35))
        for r, row in enumerate(rows):
            ws = [measure(words[k], size, 'display') for k in row]
            tw = sum(ws) + sp * (len(row) - 1)
            x = CX - tw / 2
            y = y0 + r * lh
            for k, wd in zip(row, ws):
                st, en = ch['wt'][k]
                active = st <= t < en
                spoken = t >= st
                col = YEL if ch['emph'][k] else WHITE
                s = 1.0 + (0.10 * (1 - prog(t, st, .14)) if active else 0)
                c.save()
                c.translate(x + wd / 2, y - size * .35); c.scale(s, s); c.translate(-(x + wd / 2), -(y - size * .35))
                g.stroke_text(c, words[k], x, y, size, 'display', col, BLACK, size * 0.16, 'left', 1.0 if spoken else 0.78)
                c.restore()
                x += wd + sp
        c.restore()

    # ---------------------------------------------------- visuals
    def vis(self, c, name, cx, cy, s, lt, seed, p=1.0):
        fn = svis.VISUALS.get(name, svis.v_question)
        c.save(); c.translate(cx, cy); c.scale(s, s)
        try:
            fn(c, lt, p, YEL, CYAN, seed)
        except Exception as e:  # never let one visual kill a render
            print('  [vis]', name, repr(e))
            svis.v_question(c, lt, 1, YEL, CYAN, seed)
        c.restore()

    def fit(self, s, maxw, size, weight='display', min_size=40):
        while measure(s, size, weight) > maxw and size > min_size:
            size -= 4
        return size

    def counter_text(self, num, lt):
        p = ease_out(prog(lt, 0.05, 0.75))
        v = num['val']
        v0 = v - 60 if num['year'] else 0
        cur = v0 + (v - v0) * p
        if num['dec']:
            s = f'{cur:,.{num["dec"]}f}' if num['comma'] else f'{cur:.{num["dec"]}f}'
        else:
            s = f'{int(round(cur)):,}' if num['comma'] else f'{int(round(cur))}'
        return num['pre'] + s + num['suf']

    def segment(self, c, t, sg, lt):
        ln = self.T['lines'][sg['line']]
        lay, seed = sg['layout'], sg['seed']
        p = 1.0
        if lay == 'hook':
            self.hook_text(c, t)
            self.vis(c, sg['vis'], CX, 935, 0.66, lt + 0.6, seed)
        elif lay == 'counter' and ln['num']:
            num = ln['num']
            s = self.counter_text(num, lt)
            final = self.counter_text(num, 99)
            size = self.fit(final, TEXT_W, 250)
            land = prog(lt, 0.8, 0.18)
            sc = 1 + 0.12 * math.sin(math.pi * land)
            glow_a = .35 + .25 * math.sin(lt * 5)
            g.glow(c, CX, 560, 380, YEL, glow_a * .6)
            c.save(); c.translate(CX, 560); c.scale(sc, sc); c.translate(-CX, -560)
            g.stroke_text(c, s, CX, 640, size, 'display', YEL, BLACK, 18, 'center')
            c.restore()
            if num['unit']:
                us = self.fit(num['unit'], TEXT_W, 76)
                g.stroke_text(c, num['unit'], CX, 760, us, 'display', CYAN, BLACK, 10, 'center', ease_out(prog(lt, .15, .3)))
            self.vis(c, sg['vis'], CX, 1010, 0.42, lt, seed)
        elif lay == 'keyword':
            te = ln['times'][ln['emph'][0]][0] if ln['emph'] else sg['t0']
            kt = t - te
            self.vis(c, sg['vis'], CX, 830, 0.9, lt, seed)
            if kt >= 0 and ln['emph_word']:
                word = re.sub(r'[^\w\'%$.-]', '', ln['emph_word']).upper().strip('.')
                size = self.fit(word, TEXT_W - 70, 170)
                sl = ease_out(prog(kt, 0, .16))
                sc = 1.7 - .7 * sl
                c.save(); c.translate(CX, 420); c.rotate(-4 + 4 * sl - 2 * math.sin(lt * 2)); c.scale(sc, sc); c.translate(-CX, -420)
                g.stroke_text(c, word, CX, 420 + size * .36, size, 'display', YEL, BLACK, 16, 'center', sl)
                c.restore()
        elif lay == 'big':
            self.vis(c, sg['vis'], CX, 760, 1.32, lt, seed)
        elif lay == 'duo':
            self.vis(c, sg['vis'], CX - 120, 850, 0.88, lt, seed)
            self.vis(c, sg['vis2'], CX + 230, 470, 0.46, lt + 1.3, seed + 1)
        else:
            self.vis(c, sg['vis'], CX, 770, 1.12, lt, seed)

    def hook_text(self, c, t):
        words = self.hook.split()
        size = 124
        while True:
            lines, cur = [], []
            for w in words:
                if cur and measure(' '.join(cur + [w]), size, 'display') > TEXT_W:
                    lines.append(cur); cur = []
                cur.append(w)
            lines.append(cur)
            if len(lines) <= 3 and all(measure(' '.join(l), size, 'display') <= TEXT_W for l in lines) or size <= 70:
                break
            size -= 6
        lh = size * 1.04
        y0 = 350 + size * .82
        wob = 1 + 0.025 * math.sin(t * 7)
        hl = self.hook_emph or {norm(max(words, key=len))}
        for r, l in enumerate(lines):
            y = y0 + r * lh
            c.save(); c.translate(CX, y - size * .35); c.scale(wob, wob); c.rotate(-2 + 1.2 * math.sin(t * 3 + r)); c.translate(-CX, -(y - size * .35))
            sp = measure(' ', size, 'display')
            tw = measure(' '.join(l), size, 'display')
            x = CX - tw / 2
            for w in l:
                col = YEL if norm(w) in hl else WHITE
                ww = g.stroke_text(c, w, x, y, size, 'display', col, BLACK, size * .15, 'left')
                x += ww + sp
            c.restore()

    def frame(self, c, t):
        T = self.T
        segs = T['segs']
        si = next((k for k, sg in enumerate(segs) if sg['t0'] <= t < sg['t1']), len(segs) - 1)
        sg = segs[si]
        lt = t - sg['t0']
        self.bg(c, t, sg)
        # camera: slow push + entrance pop + punch-in & shake on emphasis
        z = 1 + 0.04 * clamp(lt / max(.5, sg['t1'] - sg['t0']))
        if si > 0:
            z *= 0.86 + 0.14 * ease_back(prog(lt, 0, .24))
        sx = sy = rot = 0.0
        for tp in T['punch']:
            d = t - tp
            if -0.06 < d < 0.6:
                k = clamp((d + .06) / .06) if d < 0 else math.exp(-d * 6)
                z += 0.12 * k
                amp = 16 * (math.exp(-d * 9) if d >= 0 else k)
                sx += amp * math.sin(t * 91); sy += amp * math.cos(t * 73); rot += 1.6 * amp / 16 * math.sin(t * 57)
        cyc = 760
        c.save()
        c.translate(CX + sx, cyc + sy); c.rotate(rot); c.scale(z, z); c.translate(-CX, -cyc)
        self.segment(c, t, sg, lt)
        c.restore()
        if si > 0 and lt < 0.12:   # flash on cut
            c.drawRect(skia.Rect.MakeWH(W, H), paint(WHITE, .22 * (1 - lt / .12)))
        self.hud(c, t)
        self.captions(c, t)

    def cover(self, c):
        T = self.T
        sg = T['segs'][0]
        self.bg(c, 1.0, sg)
        self.hook_text(c, 0.0)
        self.vis(c, sg['vis'], CX, 960, 0.8, 1.2, sg['seed'])
        self.hud(c, 0)


# ================================================================ render
STATE = {}


def render_range(args):
    f0, f1, path = args
    sc = STATE['scene']
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-'] + X264 + ['-threads', '1', path]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        c.clear(skia.Color4f(0, 0, 0, 1))
        sc.frame(c, f / FPS)
        ff.stdin.write(surf.makeImageSnapshot().tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError('ffmpeg failed')
    return path


def save_png(surf, path):
    import numpy as np
    from PIL import Image
    arr = np.frombuffer(surf.makeImageSnapshot().tobytes(), np.uint8).reshape(H, W, 4)[:, :, [2, 1, 0]]
    Image.fromarray(arr).save(path)


def render_short(short, out_dir, voice, speed, jobs, stills=None):
    slug = short.get('slug') or f"day{short.get('day')}"
    day = short.get('day', '?')
    os.makedirs(out_dir, exist_ok=True)
    build_dir = os.path.join(out_dir, '.build', slug)
    os.makedirs(build_dir, exist_ok=True)
    t0 = time.time()
    print(f'== day {day}: {slug}')
    T = build(short, os.path.join(out_dir, '.build', 'tts'), voice, speed)
    nf = int(math.ceil(T['total'] * FPS))
    print(f'  {T["total"]:.1f}s, {len(T["segs"])} segments, {len(T["chunks"])} caption chunks, speed {T["speed"]:.2f}')
    print('  segs:', ' | '.join(f'{s["t0"]:.1f} {s["layout"]}:{s["vis"]}' for s in T['segs']))
    sc = Scene(short, T, day)
    STATE['scene'] = sc
    # SRT (English only; YouTube auto-translates)
    cues = []
    for ln in T['lines']:
        cues += subs.chunk_line(ln['en'], ln['start'], ln['end'], 42)
    subs.write_srt(os.path.join(out_dir, f'{slug}_en.srt'), cues)
    # cover
    surf = skia.Surface(W, H)
    sc.cover(surf.getCanvas())
    save_png(surf, os.path.join(out_dir, f'{slug}_cover.png'))
    if stills is not None:
        for f in stills:
            c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 1)); sc.frame(c, f / FPS)
            save_png(surf, os.path.join(out_dir, f'{slug}_f{f:05d}.png'))
        return T
    # audio
    wav = os.path.join(build_dir, 'mix.wav')
    saudio.mix(T['placements'], T['cuts'], T['punch'], nf / FPS, wav)
    # video in parallel ranges
    n = max(1, jobs)
    edges = [round(nf * k / n) for k in range(n + 1)]
    parts = [(edges[k], edges[k + 1], os.path.join(build_dir, f'part{k}.mp4')) for k in range(n)]
    with Pool(n) as pool:
        pool.map(render_range, parts)
    lst = os.path.join(build_dir, 'list.txt')
    with open(lst, 'w') as f:
        for _, _, p in parts:
            f.write(f"file '{p}'\n")
    vid = os.path.join(build_dir, 'video.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', vid], check=True)
    out = os.path.join(out_dir, f'{slug}.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vid, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-af', 'aresample=48000,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000', '-c:a', 'aac', '-b:a', '192k',
                    '-ac', '2', '-movflags', '+faststart', '-shortest', out + '.tmp.mp4'], check=True)
    os.replace(out + '.tmp.mp4', out)
    print(f'  done {out} ({T["total"]:.1f}s) in {time.time() - t0:.0f}s')
    return T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('json'); ap.add_argument('day'); ap.add_argument('out_dir', nargs='?')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--voice', default='am_fenrir')
    ap.add_argument('--speed', type=float, default=1.15)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--stills', help='comma-separated frame numbers: write PNG stills instead of video')
    a = ap.parse_args()
    if a.day == '--all' or a.all:
        if a.day not in ('--all',) and a.out_dir is None:
            a.out_dir = a.day
    data = json.load(open(a.json, encoding='utf-8'))
    if isinstance(data, dict):
        data = data.get('shorts', [data])
    stills = [int(x) for x in a.stills.split(',')] if a.stills else None
    if a.all:
        todo = data
        out = a.out_dir or a.day
    else:
        todo = [s for s in data if str(s.get('day')) == str(a.day)]
        out = a.out_dir
        if not todo:
            sys.exit(f'day {a.day} not found')
    for s in todo:
        render_short(s, out, a.voice, a.speed, a.jobs, stills)


if __name__ == '__main__':
    main()
