#!/usr/bin/env python3
"""Render an explainer video from a scenes.json.

usage: python3 engine/render.py <scenes.json> <out_dir> [--name NAME] [--voice am_michael]
                                [--speed 1.0] [--no-pad] [--jobs 2] [--preview SECONDS]

scenes.json: [{"id","chapter","lines":[{"en","es"}],"visual","on_screen_text", optional "type","icon"}]
Outputs <out_dir>/<name>.mp4, <name>_es.srt, <name>_en.srt (name defaults to the scenes.json folder name).
Per-scene segments are cached in <out_dir>/.build so re-renders only redo changed scenes.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx  # noqa: E402
from gfx import W, H, FPS, text, rrect, rgb, paint, measure, prog, ease_out, MUTED, AMBER, WHITE  # noqa: E402
import visuals  # noqa: E402
import subs  # noqa: E402

LINE_GAP = 0.25
SCENE_GAP = 0.6
LEAD = 0.35
CHAPTER_DUR = 2.4
END_DUR = 4.0
BRAND = 'ODDLY PROVEN'
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
X264 = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-g', '60',
        '-r', str(FPS), '-video_track_timescale', '15360']


def engine_hash():
    h = hashlib.sha1()
    for f in sorted(os.listdir(ENGINE_DIR)):
        if f.endswith('.py') and f not in ('audio.py', 'thumbnail.py', 'subs.py'):  # cues are part of each segment key
            h.update(open(os.path.join(ENGINE_DIR, f), 'rb').read())
    return h.hexdigest()[:10]


import re
CH_RE = re.compile(r'^\s*chapter\s*(\d+)\s*[:.\-–—]\s*(.+)$', re.I)


def is_intro_chapter(name):
    n = (name or '').lower()
    return any(k in n for k in ('hook', 'intro', 'cold open', 'opening', 'teaser'))


def chapter_info(name, numbered_mode):
    """-> (show_card, number or None, title, hud_label)"""
    m = CH_RE.match(name or '')
    if m:
        return True, int(m.group(1)), m.group(2).strip(), f'Ch {int(m.group(1))} \u00b7 {m.group(2).strip()}'
    if numbered_mode:
        return False, None, name, name
    return (not is_intro_chapter(name)), None, name, name


def apply_overrides(scenes, path):
    if not path or not os.path.exists(path):
        return scenes
    ov = json.load(open(path, encoding='utf-8'))
    print(f'      visual overrides: {path} ({len(ov)} scenes)')
    out = []
    for sc in scenes:
        o = ov.get(str(sc.get('id')))
        sc = dict(sc)
        if o:
            for k in ('type', 'spec', 'on_screen_text', 'icon'):
                if k in o:
                    sc[k] = o[k]
        out.append(sc)
    return out


# ---------------------------------------------------------------- timeline
def build_timeline(scenes, cache_dir, voice, speed):
    import audio
    units, placements, es_cues, en_cues = [], [], [], []
    t = 0.0
    prev_ch, ch_num, prev_kind = None, 0, None
    numbered = any(CH_RE.match(s.get('chapter') or '') for s in scenes)
    hud = ''
    n_lines = sum(len(s.get('lines', [])) for s in scenes)
    done = 0
    for si, sc in enumerate(scenes):
        ch = sc.get('chapter', '')
        if ch and ch != prev_ch:
            show, num, title, hud = chapter_info(ch, numbered)
            if show and not (si == 0 and is_intro_chapter(ch)):
                ch_num = num if num is not None else ch_num + 1
                cs = dict(sc, _chapter_num=ch_num, _chapter_title=title)
                units.append(dict(kind='chapter', scene=cs, items=[], start=t, dur=CHAPTER_DUR, beats=[], mirror=False,
                                  index=len(units), chapter=hud))
                t += CHAPTER_DUR
            prev_ch = ch
        items = visuals.norm_items(sc.get('on_screen_text'))
        st = t
        lt = LEAD
        beats = []
        for ln in sc.get('lines', []):
            en, es = ln.get('en', '').strip(), ln.get('es', '').strip()
            if not en:
                continue
            x = audio.tts(en, cache_dir, voice, speed)
            done += 1
            print(f'\r  tts {done}/{n_lines}', end='', flush=True)
            d = len(x) / audio.SR
            placements.append((st + lt, x))
            beats.append(lt)
            a, b = st + lt, st + lt + d
            es_cues += subs.chunk_line(es or en, a, b)
            en_cues += subs.chunk_line(en, a, b)
            lt += d + LINE_GAP
        dur = lt - LINE_GAP + SCENE_GAP if beats else 3.0
        kind = visuals.choose_type(sc, items, prev_kind)
        units.append(dict(kind=kind, scene=sc, items=items, start=st, dur=dur, beats=beats,
                          mirror=(si % 2 == 1), index=len(units), chapter=hud))
        prev_kind = kind
        t = st + dur
    print()
    units.append(dict(kind='end', scene={'id': 'end'}, items=[], start=t, dur=END_DUR, beats=[], mirror=False,
                      index=len(units), chapter=''))
    t += END_DUR
    # frame quantization: each unit spans integer frames, contiguous
    for u in units:
        u['f0'] = int(round(u['start'] * FPS))
    for i, u in enumerate(units):
        f1 = units[i + 1]['f0'] if i + 1 < len(units) else int(round(t * FPS))
        u['nframes'] = f1 - u['f0']
    # cues: extend each cue until next cue (max +0.5s) for readability
    for cues in (es_cues, en_cues):
        for i, c in enumerate(cues):
            nxt = cues[i + 1]['start'] if i + 1 < len(cues) else c['end'] + .6
            c['end'] = min(max(c['end'], c['start'] + 1.0), nxt - 0.04, c['end'] + 0.5) if nxt - .04 > c['start'] else c['end']
    return units, placements, es_cues, en_cues, t


# ---------------------------------------------------------------- drawing
_bg = None


def draw_hud(c, u, gt, total, lt):
    a = 0.85
    rrect(c, 80, 56, 14, 14, 3, AMBER, a)
    text(c, BRAND, 108, 70, 17, 'bold', MUTED, a, tracking=3)
    ch = u.get('chapter') or ''
    if ch and u['kind'] != 'chapter':
        lab = ch.upper()
        if len(lab) > 46:
            lab = lab[:46].rsplit(' ', 1)[0].rstrip(',') + '\u2026'
        text(c, lab, W - 80, 70, 17, 'bold', MUTED, a * ease_out(prog(lt, 0, .6)), 'right', tracking=3)
    # progress line
    rrect(c, 0, 0, W, 5, 0, '#1A2747', 1)
    rrect(c, 0, 0, W * min(1, gt / total), 5, 0, AMBER, .9)


SUB_SIZE = 44
SUB_LH = 58


def draw_subs(c, cues, gt):
    for cue in cues:
        if cue['start'] <= gt < cue['end']:
            lines = cue['lines']
            a = min(1, (gt - cue['start']) / 0.12, (cue['end'] - gt) / 0.12)
            w = max(measure(l, SUB_SIZE, 'semibold') for l in lines) + 56
            h = len(lines) * SUB_LH + 26
            y0 = 1042 - h
            rrect(c, W / 2 - w / 2, y0, w, h, 14, '#050A16', 0.72 * a)
            for i, l in enumerate(lines):
                text(c, l, W / 2, y0 + 13 + SUB_LH * (i + 1) - 15, SUB_SIZE, 'semibold', WHITE, a, 'center')
            break


def render_unit(job):
    global _bg
    u, total, cues, path = job['unit'], job['total'], job['cues'], job['path']
    if os.path.exists(path):
        return path, 0.0
    import skia
    if _bg is None:
        _bg = gfx.Background()
    t0 = time.time()
    vis = visuals.make_visual(u['kind'], u['scene'], u['items'], u['nframes'] / FPS, u['beats'], u['mirror'], u['index'])
    tmp = path[:-4] + '.tmp.mp4'
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-'] + X264 + ['-threads', '2', tmp]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    dur = u['nframes'] / FPS
    my = [q for q in cues if q['end'] > u['start'] - 1 and q['start'] < u['start'] + dur + 1]
    frames_only = job.get('frames')
    for fi in range(u['nframes']):
        if frames_only is not None and fi not in frames_only:
            continue
        lt = fi / FPS
        gt = (u['f0'] + fi) / FPS
        _bg.draw(c, gt, accent_shift=1.0 if u['kind'] in ('chapter', 'end') else 0.0)
        out = gfx.ease_in_out(prog(lt, dur - 0.4, 0.4)) if u['kind'] not in ('chapter', 'end') else 0
        if out > 0:
            c.saveLayerAlpha(None, int(255 * (1 - out)))
            c.translate(0, -24 * out)
        else:
            c.save()
        try:
            vis.draw(c, lt)
        except Exception as e:
            print(f'  [draw] {u["kind"]} scene {u["scene"].get("id")} failed at {lt:.2f}s: {e!r}; using icon fallback', flush=True)
            sc = dict(u['scene']); sc.pop('spec', None)
            vis = visuals.IconCaption(sc, u['items'], dur, u['beats'], u['mirror'], u['index'])
            vis.draw(c, lt)
        c.restore()
        if u['kind'] != 'end':
            draw_hud(c, u, gt, total, lt)
        draw_subs(c, my, gt)
        buf = surf.makeImageSnapshot().tobytes()
        if frames_only is not None:
            import numpy as np
            from PIL import Image
            arr = np.frombuffer(buf, np.uint8).reshape(H, W, 4)[:, :, [2, 1, 0]]
            Image.fromarray(arr).save(f"{job['frames_dir']}/u{u['index']:03d}_{u['kind']}_{fi:05d}.png")
            continue
        ff.stdin.write(buf)
    ff.stdin.close()
    rc = ff.wait()
    if frames_only is not None:
        if os.path.exists(tmp):
            os.remove(tmp)
        return path, time.time() - t0
    if rc != 0:
        raise RuntimeError(f'ffmpeg failed for unit {u["index"]}')
    os.replace(tmp, path)
    return path, time.time() - t0


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scenes'); ap.add_argument('out_dir')
    ap.add_argument('--name'); ap.add_argument('--voice', default='am_michael')
    ap.add_argument('--speed', type=float, default=1.0); ap.add_argument('--no-pad', action='store_true')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--no-burn', action='store_true', help='do not burn subtitles into the video')
    ap.add_argument('--visuals', help='per-scene visual overrides JSON {id: {type, spec, on_screen_text}}; default <out_dir>/<name>_visuals.json or <scenes_dir>/visuals.json')
    ap.add_argument('--only', help='with --stills: comma-separated scene ids to render')
    ap.add_argument('--stills', help='only render PNG stills at these comma-separated local fractions (e.g. 0.3,0.9) of every unit into DIR=out_dir/stills')
    a = ap.parse_args()
    scenes = json.load(open(a.scenes, encoding='utf-8'))
    name = a.name or os.path.basename(os.path.dirname(os.path.abspath(a.scenes))) or 'video'
    os.makedirs(a.out_dir, exist_ok=True)
    build = os.path.join(a.out_dir, '.build', name)
    os.makedirs(build, exist_ok=True)
    t0 = time.time()
    vpath = a.visuals
    if not vpath:
        for cand in (os.path.join(a.out_dir, f'{name}_visuals.json'), os.path.join(os.path.dirname(os.path.abspath(a.scenes)), 'visuals.json')):
            if os.path.exists(cand):
                vpath = cand; break
    scenes = apply_overrides(scenes, vpath)
    print(f'[1/5] narration + timeline ({len(scenes)} scenes)')
    units, placements, es_cues, en_cues, total = build_timeline(scenes, os.path.join(a.out_dir, '.build', 'tts'), a.voice, a.speed)
    print(f'      total {total:.1f}s, {len(units)} units:', ' '.join(u['kind'] for u in units))
    subs.write_srt(os.path.join(a.out_dir, f'{name}_es.srt'), es_cues)
    subs.write_srt(os.path.join(a.out_dir, f'{name}_en.srt'), en_cues)
    eh = engine_hash()
    burn = [] if a.no_burn else es_cues
    jobs = []
    for u in units:
        spec = json.dumps([u, total, [q for q in burn if q['end'] > u['start'] - 1 and q['start'] < u['start'] + u['dur'] + 1], eh], sort_keys=True, default=str)
        key = hashlib.sha1(spec.encode()).hexdigest()[:10]
        jobs.append(dict(unit=u, total=total, cues=burn, path=os.path.join(build, f'u{u["index"]:03d}_{key}.mp4')))
    if a.stills:
        sd = os.path.join(a.out_dir, 'stills'); os.makedirs(sd, exist_ok=True)
        fr = [float(x) for x in a.stills.split(',')]
        if a.only:
            keep = set(a.only.split(','))
            jobs = [j for j in jobs if str(j['unit']['scene'].get('id')) in keep]
        for j in jobs:
            j['frames'] = {min(j['unit']['nframes'] - 1, int(f * j['unit']['nframes'])) for f in fr}
            j['frames_dir'] = sd
            j['path'] = j['path'][:-4] + '.still.mp4'
        with Pool(a.jobs) as pool:
            list(pool.imap_unordered(render_unit, jobs))
        print('stills in', sd)
        return
    print('[2/5] audio mix')
    import audio
    wav = os.path.join(build, 'mix.wav')
    audio.build_track(placements, units[-1]['f0'] / FPS + units[-1]['nframes'] / FPS, wav, pad=not a.no_pad)
    print(f'[3/5] rendering {len(jobs)} segments on {a.jobs} workers')
    order = sorted(jobs, key=lambda j: -j['unit']['nframes'])
    done = 0
    with Pool(a.jobs) as pool:
        for path, dt in pool.imap_unordered(render_unit, order):
            done += 1
            print(f'      {done}/{len(jobs)} {os.path.basename(path)} {dt:.0f}s  (elapsed {time.time() - t0:.0f}s)', flush=True)
    # clean stale segments
    keep = {os.path.basename(j['path']) for j in jobs}
    for f in os.listdir(build):
        if f.startswith('u') and f.endswith('.mp4') and f not in keep:
            os.remove(os.path.join(build, f))
    print('[4/5] concat')
    lst = os.path.join(build, 'list.txt')
    with open(lst, 'w') as f:
        for j in jobs:
            f.write(f"file '{os.path.abspath(j['path'])}'\n")
    vid = os.path.join(build, 'video.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', vid], check=True)
    print('[5/5] mux audio')
    out = os.path.join(a.out_dir, f'{name}.mp4')
    tmp = out[:-4] + '.tmp.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vid, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-af', 'aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
                    '-movflags', '+faststart', '-shortest', tmp], check=True)
    os.replace(tmp, out)
    print(f'done: {out}  ({total:.1f}s video, {time.time() - t0:.0f}s wall)')


if __name__ == '__main__':
    main()
