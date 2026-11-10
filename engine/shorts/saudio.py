"""Shorts audio: per-line kokoro TTS (cached), synthesized beat + whoosh/pop SFX, ducked mix."""
import hashlib
import os
import wave
import numpy as np
from scipy.signal import lfilter, butter

SR = 24000
TTS_DIR = os.environ.get('KOKORO_DIR', '/home/claude/channel/tts')
_k = None


def _engine():
    global _k
    if _k is None:
        from kokoro_onnx import Kokoro
        _k = Kokoro(os.path.join(TTS_DIR, 'kokoro-v1.0.onnx'), os.path.join(TTS_DIR, 'voices-v1.0.bin'))
    return _k


def trim(x, thr=0.008, head=0.02, tail=0.03):
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    return x[max(0, idx[0] - int(head * SR)): min(len(x), idx[-1] + int(tail * SR))]


def tts(text, cache, voice, speed):
    os.makedirs(cache, exist_ok=True)
    key = hashlib.sha1(f'{voice}|{speed:.3f}|{text}'.encode()).hexdigest()[:16]
    p = os.path.join(cache, key + '.npy')
    if os.path.exists(p):
        return np.load(p)
    s, sr = _engine().create(text, voice=voice, speed=speed, lang='en-us')
    x = trim(np.asarray(s, np.float32))
    np.save(p, x)
    return x


# ---------------------------------------------------------------- synth
def _env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def whoosh(dur=0.32, seed=0):
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    t = np.linspace(0, 1, n)
    out = np.zeros(n)
    # sweeping band-pass via short blocks
    blk = 256
    for i in range(0, n, blk):
        f = 400 + 5000 * t[i] ** 1.5
        b, a = butter(2, [max(50, f * .6) / (SR / 2), min(0.95, f * 1.4 / (SR / 2))], 'band')
        out[i:i + blk] = lfilter(b, a, x[i:i + blk])
    env = np.sin(np.pi * t) ** 2
    out = out * env
    return (out / (np.max(np.abs(out)) + 1e-9)).astype(np.float32)


def pop(f0=900, dur=0.09):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * np.exp(-t * 25) + 300
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * _env(n, .002, .025)).astype(np.float32)


def beat(dur, bpm=124, seed=1):
    n = int(dur * SR) + SR
    out = np.zeros(n, np.float32)
    spb = 60 / bpm
    rng = np.random.default_rng(seed)
    # kick
    kn = int(.25 * SR); kt = np.arange(kn) / SR
    kick = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-kt * 30)) / SR) * np.exp(-kt * 14)
    hn = int(.05 * SR)
    b, a = butter(2, 7000 / (SR / 2), 'high')
    hat = lfilter(b, a, rng.normal(0, 1, hn)) * np.exp(-np.arange(hn) / SR * 70)
    cn = int(.18 * SR)
    b2, a2 = butter(2, [900 / (SR / 2), 3500 / (SR / 2)], 'band')
    clap = lfilter(b2, a2, rng.normal(0, 1, cn)) * np.exp(-np.arange(cn) / SR * 22)
    roots = [55.0, 43.65, 65.41, 49.0]  # A F C G
    bn = int(spb / 2 * SR); bt = np.arange(bn) / SR
    i = 0
    tt = 0.0
    while tt < dur:
        s = int(tt * SR)
        beat_i = i % 4
        def add(sig, g):
            j = min(n, s + len(sig)); out[s:j] += g * sig[:j - s]
        add(kick, .9)
        if beat_i in (1, 3):
            add(clap, .35)
        # offbeat hat + bass
        so = int((tt + spb / 2) * SR)
        if so < n:
            j = min(n, so + hn); out[so:j] += .25 * hat[:j - so]
            r = roots[(i // 8) % 4] * 2
            bass = (np.sign(np.sin(2 * np.pi * r * bt)) * .4 + np.sin(2 * np.pi * r * bt)) * np.exp(-bt * 9)
            b3, a3 = butter(2, 900 / (SR / 2))
            bass = lfilter(b3, a3, bass)
            j = min(n, so + bn); out[so:j] += .5 * bass[:j - so]
        # 16th hats light
        s16 = int((tt + spb * .25) * SR)
        if s16 < n:
            j = min(n, s16 + hn); out[s16:j] += .1 * hat[:j - s16]
        i += 1
        tt += spb
    return out[:int(dur * SR)] / (np.max(np.abs(out)) + 1e-9)


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


def mix(placements, cuts, pops, total, path, music_db=-17.0, sfx_db=-14.0):
    n = int(total * SR)
    v = np.zeros(n, np.float32); mask = np.zeros(n, np.float32)
    for st, x in placements:
        i = int(st * SR); j = min(n, i + len(x))
        v[i:j] += x[:j - i]; mask[i:j] = 1
    sp = v[mask > 0]
    v *= 0.1 / (np.sqrt(np.mean(sp ** 2)) + 1e-9)           # voice ~ -20 dBFS RMS
    m = beat(total)
    m /= np.sqrt(np.mean(m ** 2)) + 1e-9
    k = int(.25 * SR)
    duck = 1 - .5 * np.convolve(mask, np.ones(k) / k, 'same')  # -6 dB while talking
    fade = np.ones(n); f = int(.4 * SR); fade[-f:] = np.linspace(1, 0, f)
    out = v + m * duck * fade * 0.1 * 10 ** (music_db / 20)
    sfx = np.zeros(n, np.float32)
    w = whoosh()
    for i, tc in enumerate(cuts):
        s = int(max(0, tc - .18) * SR); j = min(n, s + len(w)); sfx[s:j] += w[:j - s]
    for tp in pops:
        pp = pop()
        s = int(tp * SR); j = min(n, s + len(pp)); sfx[s:j] += .8 * pp[:j - s]
    out += sfx * 0.1 * 10 ** (sfx_db / 20) * 3.0
    pk = np.max(np.abs(out))
    if pk > .97:
        out *= .97 / pk
    write_wav(path, out)
