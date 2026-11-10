"""Subtitle chunking (<=2 lines x ~42 chars), timing and SRT output."""
import re

MAXL = 42
STOP = set('''a al de del el la las los lo un una unos unas y o e u que en con por para se su sus sin como mas más pero ni
the a an of to in on at by for and or but with from as is was were that which who their his her its your our my this these those'''.split())
NUMW = set('''veinte treinta cuarenta cincuenta sesenta setenta ochenta noventa cien ciento doscientos trescientos mil
uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis diecisiete dieciocho diecinueve veintidós
twenty thirty forty fifty sixty seventy eighty ninety hundred thousand one two three four five six seven eight nine ten eleven twelve seventeen'''.split())


def _split_long(s, maxc):
    """Split text into pieces <= maxc chars, preferring sentence > clause > word boundaries."""
    s = s.strip()
    if len(s) <= maxc:
        return [s]
    for pat in (r'(?<=[.!?…])\s+', r'(?<=[,;:—–])\s+'):
        parts = [p for p in re.split(pat, s) if p.strip()]
        if len(parts) > 1:
            out, cur = [], ''
            for p in parts:
                t = (cur + ' ' + p).strip()
                if len(t) <= maxc:
                    cur = t
                else:
                    if cur:
                        out.append(cur)
                    cur = p
            if cur:
                out.append(cur)
            if all(len(o) <= maxc for o in out):
                return out
            res = []
            for o in out:
                res += _split_long(o, maxc)
            return res
    # balanced word split
    words = s.split()
    n = max(2, -(-len(s) // maxc))
    target = len(s) / n
    out, cur = [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if len(t) > target and cur and len(out) < n - 1:
            # never end a chunk on a dangling function word: carry it over
            cw = cur.split()
            carry = []
            while len(cw) > 1 and (cw[-1].lower() in STOP or
                                   (cw[-1].lower().strip(',') in NUMW and (carry[0] if carry else w).lower() in ('y', 'por', 'ciento', 'percent', 'mil'))):
                carry.insert(0, cw.pop())
            out.append(' '.join(cw)); cur = ' '.join(carry + [w])
        else:
            cur = t
    out.append(cur)
    res = []
    for o in out:
        res += _split_long(o, maxc) if len(o) > maxc and ' ' in o else [o]
    return res


def two_lines(s, maxl=MAXL):
    """Break a chunk into at most 2 balanced lines."""
    if len(s) <= maxl:
        return [s]
    words = s.split()
    best = None
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        score = max(len(a), len(b)) + (0 if len(a) <= maxl and len(b) <= maxl else 100) + (12 if words[i - 1].lower() in STOP else 0)
        if best is None or score < best[0]:
            best = (score, [a, b])
    return best[1]


def chunk_line(text, start, end, maxl=MAXL):
    chunks = _split_long(text, maxl * 2)
    total = sum(len(c) for c in chunks) or 1
    cues, t = [], start
    for c in chunks:
        d = (end - start) * len(c) / total
        cues.append(dict(start=t, end=t + d, lines=two_lines(c, maxl)))
        t += d
    return cues


def fmt_ts(x):
    ms = int(round(x * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def write_srt(path, cues):
    with open(path, 'w', encoding='utf-8') as f:
        for i, c in enumerate(cues, 1):
            f.write(f"{i}\n{fmt_ts(c['start'])} --> {fmt_ts(c['end'])}\n" + '\n'.join(c['lines']) + '\n\n')
