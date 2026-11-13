"""Find scene start times in an ElevenLabs voiceover.

The script is one paragraph per scene. Paragraph breaks are usually the longest
pauses, but not always: a dramatic pause inside a paragraph ("It comes back...
empty.") can be longer than a paragraph break. So when the clean script is given,
each paragraph break is matched to the pause nearest to where that paragraph should
start (estimated from its share of the script's characters), preferring longer pauses.

usage:
  python3 tools/scene_times.py voice.mp3 --script episodes/NNN-slug/clean.txt   # recommended
  python3 tools/scene_times.py voice.mp3 --scenes 7                              # fallback: longest pauses
  options: --noise -35 (dB)  --min 0.3 (s, shortest pause considered)
prints JSON: {"duration", "scenes": [{"start", "end", "text"?}], "silences": [...], "method"}

clean.txt = the CLEAN script (no [tags]), paragraphs separated by a blank line. Any
[tags] left in it are ignored.
"""
import argparse, json, re, subprocess


def detect(path, noise, min_d):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", f"silencedetect=noise={noise}dB:d={min_d}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    duration = int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3])
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    if len(starts) > len(ends):  # silence running to the end of the file
        ends.append(duration)
    return duration, [{"start": max(0.0, s), "end": e, "len": round(e - max(0.0, s), 3)} for s, e in zip(starts, ends)]


def read_paragraphs(path):
    text = open(path, encoding="utf-8").read()
    paras = [re.sub(r"\[[^\]]*\]", "", p) for p in re.split(r"\n\s*\n", text)]
    paras = [re.sub(r"\s+", " ", p).strip() for p in paras]
    return [p for p in paras if re.search(r"[A-Za-z0-9]", p)]


def speech_bounds(sil, duration):
    lead = next((s["end"] for s in sil if s["start"] <= 0.05), 0.0)
    tail = next((s["start"] for s in sil if s["end"] >= duration - 0.05), duration)
    return lead, tail


def pick_longest(inner, n_cuts):
    return sorted(sorted(inner, key=lambda s: -s["len"])[:n_cuts], key=lambda s: s["start"])


def pick_aligned(inner, paras, lead, tail):
    """Choose one pause per paragraph break, in order, minimising distance to the expected
    break time (by character share) and rewarding longer pauses. Dynamic programming."""
    n_cuts = len(paras) - 1
    chars = [len(p) for p in paras]
    total = sum(chars)
    span = tail - lead
    avg = span / len(paras)
    expected, acc = [], 0
    for c in chars[:-1]:
        acc += c
        expected.append(lead + span * acc / total)
    m = len(inner)
    if m < n_cuts:
        return None

    def cost(k, j):
        s = inner[j]
        mid = (s["start"] + s["end"]) / 2
        return abs(mid - expected[k]) / avg - 0.6 * min(s["len"], 1.5)

    INF = float("inf")
    best = [[INF] * m for _ in range(n_cuts)]
    prev = [[-1] * m for _ in range(n_cuts)]
    for j in range(m):
        best[0][j] = cost(0, j)
    for k in range(1, n_cuts):
        run_min, run_arg = INF, -1
        for j in range(m):
            if j - 1 >= 0 and best[k - 1][j - 1] < run_min:
                run_min, run_arg = best[k - 1][j - 1], j - 1
            if run_arg >= 0:
                best[k][j] = run_min + cost(k, j)
                prev[k][j] = run_arg
    j = min(range(m), key=lambda x: best[n_cuts - 1][x])
    if best[n_cuts - 1][j] == INF:
        return None
    picks = []
    for k in range(n_cuts - 1, -1, -1):
        picks.append(inner[j])
        j = prev[k][j]
    return list(reversed(picks))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp3")
    ap.add_argument("--script", help="clean script, one paragraph per scene, blank line between paragraphs")
    ap.add_argument("--scenes", type=int, help="number of paragraphs (fallback when no --script)")
    ap.add_argument("--noise", type=float, default=-35)
    ap.add_argument("--min", type=float, default=0.3)
    a = ap.parse_args()
    if not a.script and not a.scenes:
        ap.error("give --script (recommended) or --scenes")

    duration, sil = detect(a.mp3, a.noise, a.min)
    lead, tail = speech_bounds(sil, duration)
    inner = [s for s in sil if s["start"] > lead and s["end"] < tail]
    paras = read_paragraphs(a.script) if a.script else None
    n = len(paras) if paras else a.scenes

    cuts, method = None, "longest-pauses"
    if paras and n > 1:
        cuts = pick_aligned(inner, paras, lead, tail)
        method = "aligned-to-script"
    if cuts is None:
        cuts, method = pick_longest(inner, n - 1), "longest-pauses"

    scenes, cur = [], lead
    for c in cuts:
        scenes.append({"start": round(cur, 3), "end": round(c["start"], 3)})
        cur = c["end"]
    scenes.append({"start": round(cur, 3), "end": round(tail, 3)})
    if paras:
        for sc, p in zip(scenes, paras):
            sc["text"] = p[:60] + ("…" if len(p) > 60 else "")
    if len(scenes) != n:
        print(f"// warning: found {len(scenes)} scenes but expected {n}; lower --min or raise --noise, and check by ear")
    print(json.dumps({"duration": round(duration, 3), "method": method, "scenes": scenes, "silences": sil}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
