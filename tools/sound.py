#!/usr/bin/env python3
"""Sound design for an episode: synthesized SFX on the page's story events, a quiet
ambient bed that follows the story's mood, ducked under the voice, loudness -14 LUFS.

  python3 tools/sound.py <episode.html> <voice.mp3> <out.mp4> --video <silent.mp4> --moods "0:tense,4.4:calm,20.8:tense,51:resolved"
  (without --video, <out> is just the audio, e.g. out.m4a)

The page exposes window.SFX = [{t, kind, gain}] (kinds: boom tick whoosh chime reject
thud flip blip end) and window.DURATION. Everything is generated here, no samples,
so every episode sounds the same family. Mood keys: calm, tense, resolved.
"""
import argparse, asyncio, pathlib, shutil, subprocess, sys, tempfile
import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100
rng = np.random.default_rng(7)


def env(n, a=.004, d=.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def tone(f, dur, a=.004, d=.2, ph=0):
    n = int(dur * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * f * t + ph) * env(n, a, d)


def mixs(*xs):
    out = np.zeros(max(len(x) for x in xs))
    for x in xs:
        out[:len(x)] += x
    return out


def noise(dur):
    return rng.standard_normal(int(dur * SR))


def band(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], btype="band", fs=SR, output="sos"), x)


def lowp(x, f):
    return sosfilt(butter(2, f, btype="low", fs=SR, output="sos"), x)


def sweep(f0, f1, dur, d=.4):
    n = int(dur * SR); t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .003, d)


def make(kind):
    if kind == "boom":    # sub drop + soft air: the hook hit
        out = .9 * sweep(90, 38, 1.6, .55); n = int(.9 * SR)
        out[:n] += .12 * lowp(noise(.9), 900) * env(n, .002, .12)
        return out
    if kind == "tick":    # a request lands in the queue
        return mixs(.22 * tone(2400, .05, .001, .012), .1 * tone(3600, .04, .001, .008))
    if kind == "whoosh":  # camera moves
        n = int(.7 * SR); t = np.arange(n) / SR
        e = np.sin(np.pi * t / .7) ** 2
        return .35 * band(noise(.7), 500, 3500) * e
    if kind == "chime":   # good number / served first
        return .32 * mixs(tone(988, 1.4, .003, .45), .5 * tone(1482, 1.2, .003, .3), .2 * tone(2964, .8, .002, .15))
    if kind == "reject":  # whole queue rejected
        n = int(.32 * SR); t = np.arange(n) / SR
        buzz = np.sign(np.sin(2 * np.pi * 98 * t)) * .5 + np.sin(2 * np.pi * 196 * t) * .5
        return .28 * lowp(buzz, 1400) * env(n, .004, .12)
    if kind == "thud":    # overload / a client gives up
        return .5 * sweep(120, 60, .25, .07)
    if kind == "flip":    # FIFO -> LIFO
        c = .3 * tone(1800, .03, .001, .006)
        out = np.zeros(int(.5 * SR)); out[:len(c)] += c; k = int(.09 * SR); out[k:k + len(c)] += c
        s = .25 * sweep(400, 1600, .4, .25); out[:len(s)] += s
        return out
    if kind == "blip":    # a response gets back to a client
        return .12 * tone(1320, .08, .002, .025)
    if kind == "end":     # end card
        return .12 * sum(tone(f, 2.4, .005, .8) for f in (523.25, 659.25, 783.99, 1046.5))
    return np.zeros(1)


MIN_GAP = {"tick": .14, "blip": .12, "thud": .2}
CHORDS = {  # mood -> chord (Hz), shades of one key so changes are smooth
    "calm": (110.0, 164.81, 220.0, 329.63),
    "tense": (98.0, 146.83, 196.0, 233.08),
    "resolved": (130.81, 196.0, 261.63, 392.0),
}


def bed(n, moods):
    t = np.arange(n) / SR
    out = np.zeros(n)
    # per-mood weight curves with 1.2 s crossfades
    keys = [(float(a), b) for a, b in moods]
    for i, (t0, m) in enumerate(keys):
        t1 = keys[i + 1][0] if i + 1 < len(keys) else 1e9
        w = np.clip((t - t0 + .6) / 1.2, 0, 1) * np.clip((t1 - t + .6) / 1.2, 0, 1)
        if not w.any():
            continue
        layer = np.zeros(n)
        for j, f in enumerate(CHORDS[m]):
            lfo = 1 + .35 * np.sin(2 * np.pi * (.07 + .03 * j) * t + j)
            layer += lfo * (np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * f * 1.003 * t + 1))
        if m == "tense":  # low rumble under overload
            layer += 2.2 * lowp(rng.standard_normal(n), 140)
        out += w * layer
    out = lowp(out, 1800)
    return out / (np.abs(out).max() + 1e-9)


def load_audio(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


async def page_data(html):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path=shutil.which("google-chrome"))
        p = await b.new_page()
        await p.goto(pathlib.Path(html).resolve().as_uri())
        d = await p.evaluate("({sfx: window.SFX || [], dur: window.DURATION})")
        await b.close()
        return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html"); ap.add_argument("voice"); ap.add_argument("out")
    ap.add_argument("--moods", default="0:calm", help="t:mood,... (calm, tense, resolved)")
    ap.add_argument("--video", help="silent render to mux the mix onto (then <out> is the final .mp4)")
    ap.add_argument("--bed", type=float, default=.05, help="bed level (linear peak) before ducking")
    a = ap.parse_args()
    d = asyncio.run(page_data(a.html))
    n = int(d["dur"] * SR) + SR
    voice = load_audio(a.voice)[:n]
    v = np.zeros(n); v[:len(voice)] = voice

    fx = np.zeros(n); last = {}
    for e in d["sfx"]:
        k, t0 = e["kind"], e["t"]
        if t0 - last.get(k, -9) < MIN_GAP.get(k, 0):
            continue
        last[k] = t0
        s = make(k) * e.get("gain", 1); i = int(t0 * SR)
        if 0 <= i < n:
            fx[i:i + len(s)] += s[:n - i]

    moods = [m.split(":") for m in a.moods.split(",")]
    b = bed(n, moods) * a.bed
    # duck bed (-9 dB) and fx (-4 dB) under the voice
    win = int(.06 * SR)
    rms = np.sqrt(np.convolve(v ** 2, np.ones(win) / win, mode="same"))
    talk = lowp(np.clip(rms / (rms.max() * .12 + 1e-9), 0, 1), 4)
    talk = np.clip(talk, 0, 1)
    mix = v + b * (1 - .65 * talk) + .55 * fx * (1 - .35 * talk)
    mix *= .5 / (np.abs(mix).max() + 1e-9)
    tmp = tempfile.mkdtemp()
    wav = f"{tmp}/mix.f32"
    mix.astype(np.float32).tofile(wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", wav,
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "2", "-c:a", "aac", "-b:a", "192k",
                    f"{tmp}/mix.m4a" if a.video else a.out], check=True)
    if a.video:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video, "-i", f"{tmp}/mix.m4a", "-map", "0:v", "-map", "1:a",
                        "-c", "copy", "-shortest", a.out], check=True)
    print(f"{a.out}: {len(d['sfx'])} events, {n / SR:.1f} s")


if __name__ == "__main__":
    main()
