"""Sound for a launch reel: a procedural music bed plus sound effects placed on the builder's cue
events, mixed to one stereo WAV. No samples and no paid API: every sound is synthesised here
with numpy, so the same reel always gets the same track.

`render_audio(project)` reads `meta.audio` (music preset, bpm, cue events, transitions) and the
duration, and returns (sample_rate, int16 stereo array). The CLI muxes it under the video.

Music presets, one per style pack:
  pop    kick on 1 and 3, claps, eighth hats, bass, a bright pluck arpeggio
  chill  soft kick, rim, warm pad, sparse keys, everything low-passed
  piano  felt piano chords and a slow arpeggio, a shaker, no drums
  uke    a strummed plucked-string pattern with a shaker and a soft kick
  synth  four on the floor, off-beat hats, a filtered saw bass and a sixteenth arpeggio

Effects: whoosh (transitions), pop (things landing), click (presses), type (typing), tick
(counters, a chime on the last), ding (notifications), thud (pain cards).
"""
from __future__ import annotations

import io
import wave

import numpy as np
from scipy import signal

SR = 44100
_MAJ, _MIN = (0, 4, 7), (0, 3, 7)

# key (midi of the tonic), progression (chord root offset, quality) one chord per bar
PRESETS = {
    "pop": dict(key=60, prog=[(0, _MAJ), (7, _MAJ), (9, _MIN), (5, _MAJ)]),
    "chill": dict(key=57, prog=[(0, _MIN), (8, _MAJ), (3, _MAJ), (10, _MAJ)]),
    "piano": dict(key=65, prog=[(0, _MAJ), (9, _MIN), (5, _MAJ), (7, _MAJ)]),
    "uke": dict(key=67, prog=[(0, _MAJ), (5, _MAJ), (9, _MIN), (7, _MAJ)]),
    "synth": dict(key=57, prog=[(0, _MIN), (5, _MIN), (8, _MAJ), (7, _MAJ)]),
}


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _t(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / max(decay, 1e-4))


def _add(buf: np.ndarray, x: np.ndarray, at: float, gain: float = 1.0):
    i = int(at * SR)
    if i >= len(buf) or i + len(x) <= 0:
        return
    if i < 0:
        x, i = x[-i:], 0
    x = x[: len(buf) - i]
    buf[i:i + len(x)] += gain * x


def _lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "low", fs=SR, output="sos"), x)


def _hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "high", fs=SR, output="sos"), x)


def _bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


# ---------------- instruments ----------------
def kick(soft=False):
    t = _t(0.35)
    f = 45 + 110 * np.exp(-t / 0.03)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.12 if soft else 0.16))
    return x * (0.6 if soft else 1.0)


def clap(rng):
    n = int(0.18 * SR)
    x = _bp(rng.standard_normal(n), 900, 2600)
    e = np.zeros(n)
    for d in (0, 0.011, 0.022):
        e += np.roll(_env(n, 0.001, 0.012), int(d * SR))
    e += 0.5 * _env(n, 0.002, 0.06)
    return 0.5 * x * e


def hat(rng, open_=False):
    n = int((0.14 if open_ else 0.05) * SR)
    return 0.22 * _hp(rng.standard_normal(n), 7000) * _env(n, 0.0005, 0.05 if open_ else 0.012)


def shaker(rng):
    n = int(0.08 * SR)
    return 0.12 * _bp(rng.standard_normal(n), 4000, 9000) * _env(n, 0.01, 0.025)


def pluck(f, dur=0.5, bright=6):
    t = _t(dur)
    x = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.3 * np.exp(-t * (4 + 3 * k)) for k in range(1, bright + 1))
    return 0.3 * x * np.clip(t / 0.003, 0, 1)


def piano(f, dur=1.6):
    t = _t(dur)
    x = 0
    for k in range(1, 8):
        fk = f * k * (1 + 0.0004 * k * k)
        x = x + np.sin(2 * np.pi * fk * t) / k ** 1.6 * np.exp(-t * (1.2 + 1.1 * k))
    return 0.32 * x * np.clip(t / 0.004, 0, 1)


def ks_string(f, dur=0.9, rng=None, damp=0.996):
    """Karplus-Strong as a comb filter: a burst of noise through a tuned, damped delay line."""
    n = int(dur * SR)
    N = max(2, int(SR / f))
    burst = np.zeros(n)
    burst[:N] = (rng.standard_normal(N) if rng is not None else np.random.default_rng(0).standard_normal(N)) * 0.5
    a = np.zeros(N + 2)
    a[0], a[N], a[N + 1] = 1, -damp / 2, -damp / 2
    y = signal.lfilter([1], a, burst)
    return 0.4 * _lp(y, 5000)


def saw(f, t):
    return 2 * ((f * t) % 1) - 1


def pad(fs, dur):
    t = _t(dur)
    x = sum(saw(f * d, t) for f in fs for d in (0.997, 1.003))
    x = _lp(x, 1400, 2) / (2 * len(fs))
    e = np.minimum(1, np.minimum(t / 0.4, (dur - t) / 0.4).clip(0))
    return 0.35 * x * e


def bass(f, dur, kind="sine"):
    t = _t(dur)
    if kind == "saw":
        x = _lp(saw(f, t) + 0.5 * saw(f * 0.5, t), 500 + 900 * np.exp(-0))
    else:
        x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
    return 0.38 * x * np.clip(t / 0.005, 0, 1) * np.exp(-t / max(dur * 0.9, 0.05))


# ---------------- music ----------------
def music(preset: str, bpm: float, seconds: float, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    P = PRESETS.get(preset, PRESETS["pop"])
    beat = 60.0 / bpm
    bar = 4 * beat
    out = np.zeros(int((seconds + 2) * SR))
    nbars = int(np.ceil(seconds / bar)) + 1
    K = kick(soft=preset in ("chill", "uke"))
    pluck_cache, piano_cache, ks_cache = {}, {}, {}
    for b in range(nbars):
        t0 = b * bar
        root, q = P["prog"][b % len(P["prog"])]
        tonic = P["key"] + root
        chord = [tonic + i for i in q]
        bass_m = tonic - 24 if tonic - 24 >= 33 else tonic - 12
        intro = b == 0
        if preset == "pop":
            for i in range(4):
                if i in (0, 2) and not intro:
                    _add(out, K, t0 + i * beat, 0.9)
                if i in (1, 3) and not intro:
                    _add(out, clap(rng), t0 + i * beat, 0.6)
            for i in range(8):
                _add(out, hat(rng, open_=(i % 4 == 2)), t0 + i * beat / 2, 0.55)
                if not intro:
                    _add(out, bass(hz(bass_m), beat / 2 * 0.9), t0 + i * beat / 2, 0.7)
            arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12]
            for i in range(8):
                m = arp[i % 4]
                x = pluck_cache.setdefault(m, pluck(hz(m), 0.45))
                _add(out, x, t0 + i * beat / 2, 0.45)
        elif preset == "chill":
            _add(out, pad([hz(m - 12) for m in chord] + [hz(chord[0])], bar + 0.3), t0, 0.9)
            if not intro:
                _add(out, K, t0, 0.7)
                _add(out, K, t0 + 2.5 * beat, 0.45)
                for i in (1, 3):
                    _add(out, _hp(clap(rng), 1500) * 0.5, t0 + i * beat, 0.5)
            for i in range(8):
                _add(out, hat(rng), t0 + i * beat / 2 + (0.02 if i % 2 else 0), 0.25)
            _add(out, bass(hz(bass_m), bar * 0.9), t0, 0.55)
            for i, m in enumerate([chord[2] + 12, chord[1] + 12, chord[0] + 24]):
                if rng.random() < 0.8:
                    x = piano_cache.setdefault(m, _lp(piano(hz(m), 1.4), 3000))
                    _add(out, x, t0 + (0.5 + i * 1.25) * beat, 0.35)
        elif preset == "piano":
            for m in chord:
                x = piano_cache.setdefault(m - 12, piano(hz(m - 12), 2.4))
                _add(out, x, t0, 0.42)
                _add(out, x, t0 + 2 * beat, 0.3)
            _add(out, piano(hz(bass_m), 2.6), t0, 0.5)
            arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[0] + 24]
            for i in range(8):
                m = arp[(i if i < 4 else 7 - i)]
                x = piano_cache.setdefault(m, piano(hz(m), 1.2))
                _add(out, x, t0 + i * beat / 2, 0.24)
            for i in range(8):
                _add(out, shaker(rng), t0 + i * beat / 2, 0.5 if i % 2 else 0.25)
        elif preset == "uke":
            strum = [1, 0, 1, 1, 0, 1, 1, 1]
            voices = sorted(chord + [chord[0] + 12])
            for i, on in enumerate(strum):
                if not on:
                    continue
                down = i % 2 == 0
                for j, m in enumerate(voices if down else voices[::-1]):
                    x = ks_cache.setdefault(m, ks_string(hz(m), 0.8, rng))
                    _add(out, x, t0 + i * beat / 2 + j * 0.012, 0.35 if down else 0.24)
            for i in range(8):
                _add(out, shaker(rng), t0 + i * beat / 2, 0.6 if i % 2 else 0.3)
            if not intro:
                _add(out, K, t0, 0.7)
                _add(out, K, t0 + 2 * beat, 0.5)
                _add(out, bass(hz(bass_m), beat * 1.8), t0, 0.5)
                _add(out, bass(hz(bass_m + 7), beat * 1.8), t0 + 2 * beat, 0.4)
        else:  # synth
            for i in range(4):
                if not intro:
                    _add(out, K, t0 + i * beat, 0.95)
                _add(out, hat(rng, open_=True), t0 + i * beat + beat / 2, 0.5)
                if not intro and i in (1, 3):
                    _add(out, clap(rng), t0 + i * beat, 0.45)
            for i in range(8):
                if not intro:
                    _add(out, bass(hz(bass_m), beat / 2 * 0.85, "saw"), t0 + i * beat / 2 + (beat / 4 if i % 2 else 0) * 0,
                         0.55)
            arp = [chord[0] + 12, chord[2] + 12, chord[1] + 24, chord[2] + 12]
            for i in range(16):
                m = arp[i % 4]
                x = pluck_cache.setdefault(m, _lp(pluck(hz(m), 0.22, 10), 3500))
                _add(out, x, t0 + i * beat / 4, 0.3)
            _add(out, pad([hz(m - 12) for m in chord], bar + 0.2), t0, 0.5)
    out = out[: int(seconds * SR)]
    fade_in = np.clip(np.arange(len(out)) / (0.25 * SR), 0, 1)
    fade_out = np.clip((len(out) - np.arange(len(out))) / (2.0 * SR), 0, 1)
    return out * fade_in * fade_out


# ---------------- effects ----------------
def whoosh(rng, dur=0.55, peak=0.6):
    """Noise through a band-pass whose centre sweeps up then down, chunk by chunk."""
    n = int(dur * SR)
    x = rng.standard_normal(n)
    y = np.zeros(n)
    C = 1024
    for i in range(0, n, C):
        u = i / n
        fc = 400 + 3200 * np.sin(np.pi * u) ** 1.5
        sos = signal.butter(2, [fc * 0.6, min(fc * 1.6, SR / 2 - 100)], "band", fs=SR, output="sos")
        y[i:i + C] = signal.sosfilt(sos, x[i:i + C])
    u = np.arange(n) / n
    e = np.where(u < peak, (u / peak) ** 2, ((1 - u) / (1 - peak)) ** 1.5)
    return 0.55 * y * e


def pop_sfx(n=1):
    t = _t(0.09)
    f = 300 + 700 * np.exp(-t / 0.018)
    return 0.45 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.001, 0.03) * min(1.4, 0.9 + 0.1 * n)


def click_sfx(rng):
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    return 0.35 * (_hp(rng.standard_normal(n), 2000) * 0.6 + np.sin(2 * np.pi * 1800 * t)) * _env(n, 0.0003, 0.006)


def key_sfx(rng):
    n = int(0.02 * SR)
    return 0.14 * _bp(rng.standard_normal(n), 2500, 7000) * _env(n, 0.0002, 0.004)


def tick_sfx():
    t = _t(0.025)
    return 0.12 * np.sin(2 * np.pi * 2600 * t) * _env(len(t), 0.0005, 0.006)


def bell(f, dur=1.2):
    t = _t(dur)
    x = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * d) for r, a, d in
            ((1, 1, 3), (2.76, 0.5, 6), (5.4, 0.25, 10), (2.0, 0.3, 4)))
    return 0.28 * x * np.clip(t / 0.002, 0, 1)


def thud_sfx(rng):
    t = _t(0.25)
    f = 60 + 60 * np.exp(-t / 0.03)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.08)
    return 0.6 * x + 0.1 * _lp(rng.standard_normal(len(t)), 600) * np.exp(-t / 0.03)


def effects(events: list[dict], seconds: float, key: int, seed: int = 11) -> np.ndarray:
    rng = np.random.default_rng(seed)
    L = np.zeros(int((seconds + 2) * SR))
    R = np.zeros_like(L)
    bell_notes = [key + 24 + i for i in (0, 4, 7, 12)]

    def put(x, at, gain=1.0, pan=0.0):
        _add(L, x, at, gain * (1 - max(0, pan)))
        _add(R, x, at, gain * (1 + min(0, pan)))

    last = {}
    for ev in sorted(events, key=lambda e: e["t"]):
        at, kind = ev["t"] / 1000.0, ev["kind"]
        if at - last.get(kind, -9) < 0.04 and kind in ("pop", "tick", "click"):
            continue
        last[kind] = at
        pan = float(rng.uniform(-0.25, 0.25))
        if kind == "whoosh":
            d = 0.75 if ev.get("tx") == "wipe" else 0.6
            put(whoosh(rng, d), at - 0.12, 0.9, pan)
        elif kind == "pop":
            put(pop_sfx(ev.get("n", 1)), at, 0.55, pan)
        elif kind == "click":
            put(click_sfx(rng), at, 0.8, pan)
        elif kind == "type":
            dur = ev.get("dur", 600) / 1000.0
            tt = 0.0
            while tt < dur:
                put(key_sfx(rng), at + tt, float(rng.uniform(0.6, 1.0)), float(rng.uniform(-0.3, 0.3)))
                tt += float(rng.uniform(0.04, 0.075))
        elif kind == "tick":
            if ev.get("final"):
                put(bell(hz(bell_notes[2]), 1.0), at, 0.45)
            else:
                put(tick_sfx(), at, 0.8, pan)
        elif kind == "ding":
            put(bell(hz(bell_notes[ev.get("n", 0) % len(bell_notes)]), 1.0), at, 0.5, pan)
        elif kind == "thud":
            put(thud_sfx(rng), at, 0.7, pan)
    n = int(seconds * SR)
    return np.stack([L[:n], R[:n]], axis=1)


# ---------------- mix ----------------
def render_audio(project: dict, music_gain: float = 0.5, sfx_gain: float = 0.85) -> tuple[int, np.ndarray]:
    meta = project.get("meta") or {}
    au = meta.get("audio") or {}
    seconds = meta.get("durationMs", 0) / 1000.0
    preset = au.get("music", "pop")
    m = music(preset, au.get("bpm", 116), seconds)
    fx = effects(au.get("events", []), seconds, PRESETS.get(preset, PRESETS["pop"])["key"])
    # duck the bed a touch under each whoosh so the transition reads
    duck = np.ones(len(m))
    for ev in au.get("events", []):
        if ev["kind"] == "whoosh":
            i = int(ev["t"] / 1000 * SR)
            w = np.hanning(int(0.6 * SR))
            seg = duck[i:i + len(w)]
            seg -= 0.35 * w[: len(seg)]
    m = m * duck.clip(0.4, 1)
    mix = music_gain * np.stack([m, m], axis=1) + sfx_gain * fx
    mix = np.tanh(mix * 1.2) / np.tanh(1.2)
    peak = np.abs(mix).max() or 1
    mix = mix / peak * 0.89
    return SR, (mix * 32767).astype(np.int16)


def wav_bytes(project: dict) -> bytes:
    sr, x = render_audio(project)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(x.tobytes())
    return buf.getvalue()
