"""Narration (kokoro-onnx, per line, cached) + synthesized ambient pad + mix."""
import hashlib
import os
import wave
import numpy as np

SR = 24000
TTS_DIR = os.environ.get('KOKORO_DIR', '/home/claude/channel/tts')
_kokoro = None


def _engine():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(os.path.join(TTS_DIR, 'kokoro-v1.0.onnx'), os.path.join(TTS_DIR, 'voices-v1.0.bin'))
    return _kokoro


def trim_silence(x, thr=0.006, margin=0.04):
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    m = int(margin * SR)
    return x[max(0, idx[0] - m): min(len(x), idx[-1] + m)]


def tts(text, cache_dir, voice='am_michael', speed=1.0):
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.sha1(f'{voice}|{speed}|{text}'.encode()).hexdigest()[:16]
    path = os.path.join(cache_dir, key + '.npy')
    if os.path.exists(path):
        return np.load(path)
    samples, sr = _engine().create(text, voice=voice, speed=speed, lang='en-us')
    x = np.asarray(samples, dtype=np.float32)
    if sr != SR:  # simple resample (kokoro is 24k already)
        n = int(len(x) * SR / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    x = trim_silence(x)
    np.save(path, x)
    return x


def ambient_pad(dur, speech_mask, level_db=-28.0, seed=3):
    """Soft evolving drone: detuned sine chord pairs + filtered noise, ducked under speech."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    chords = [[110.0, 164.81, 220.0, 261.63], [98.0, 146.83, 196.0, 246.94],
              [87.31, 130.81, 174.61, 220.0], [103.83, 155.56, 207.65, 261.63]]
    period = 14.0
    out = np.zeros(n, np.float32)
    for k, ch in enumerate(chords):
        # each chord has a raised-cosine window in a rotating cycle
        phase = (t / period - k) % len(chords)
        win = np.where(phase < 2, 0.5 - 0.5 * np.cos(np.pi * phase), 0.0)
        s = np.zeros(n)
        for i, f in enumerate(ch):
            lfo = 0.6 + 0.4 * np.sin(2 * np.pi * (0.05 + 0.013 * i) * t + i)
            s += lfo * (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.003 * t + 1.3)) / (1 + i * .35)
        out += (win * s).astype(np.float32)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n).astype(np.float32)
    # one-pole low-pass ~300 Hz, vectorized via cumulative filter on blocks
    a = np.exp(-2 * np.pi * 300 / SR)
    from scipy.signal import lfilter  # noqa
    noise = lfilter([1 - a], [1, -a], noise).astype(np.float32)
    out = out / (np.max(np.abs(out)) + 1e-9) + 0.25 * noise / (np.max(np.abs(noise)) + 1e-9)
    out /= np.sqrt(np.mean(out ** 2)) + 1e-9          # unit RMS
    out *= 10 ** (level_db / 20)                     # relative to a ~0 dB RMS reference (voice is normalized to ~-20 dBFS RMS below)
    # duck under speech (-6 dB), smoothed
    duck = 1.0 - 0.5 * speech_mask[:n]
    k = int(0.4 * SR)
    duck = np.convolve(duck, np.ones(k) / k, mode='same')
    # fade in/out
    f = int(2.0 * SR)
    env = np.ones(n); env[:f] = np.linspace(0, 1, f); env[-f:] = np.linspace(1, 0, f)
    return (out * duck * env).astype(np.float32)


def write_wav(path, x, sr=SR):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def build_track(placements, total_dur, out_path, pad=True):
    """placements: list of (start_sec, samples)."""
    n = int(total_dur * SR) + SR
    voice = np.zeros(n, np.float32)
    mask = np.zeros(n, np.float32)
    for st, x in placements:
        i = int(round(st * SR))
        j = min(n, i + len(x))
        voice[i:j] += x[:j - i]
        mask[i:j] = 1
    # normalize voice to ~ -20 dBFS RMS over speech
    sp = voice[mask > 0]
    rms = np.sqrt(np.mean(sp ** 2)) if len(sp) else 1
    voice *= 0.1 / (rms + 1e-9)
    mix = voice.copy()
    if pad:
        try:
            mix += ambient_pad(n / SR, mask) * 0.1  # pad level is relative to voice RMS (0.1)
        except Exception as e:
            print('  [audio] pad skipped:', e)
    peak = np.max(np.abs(mix))
    if peak > 0.97:
        mix *= 0.97 / peak
    write_wav(out_path, mix[:int(total_dur * SR)])
