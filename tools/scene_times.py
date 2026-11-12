"""Find scene start times in an ElevenLabs voiceover.

The script is written one paragraph per scene with a blank line between
paragraphs, so the longest silences in the MP3 are the scene boundaries.

usage: python3 tools/scene_times.py voice.mp3 --scenes 7 [--noise -35] [--min 0.35]
prints JSON: {"duration": s, "scenes": [{"start": s, "end": s}, ...], "silences": [...]}
"""
import argparse, json, re, subprocess


def detect(path, noise, min_d):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", f"silencedetect=noise={noise}dB:d={min_d}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    duration = int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    sil = [{"start": s, "end": e, "len": round(e - s, 3)} for s, e in zip(starts, ends)]
    return duration, sil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp3")
    ap.add_argument("--scenes", type=int, required=True, help="number of paragraphs in the script")
    ap.add_argument("--noise", type=float, default=-35)
    ap.add_argument("--min", type=float, default=0.35)
    a = ap.parse_args()
    duration, sil = detect(a.mp3, a.noise, a.min)
    # ignore leading/trailing silence, then take the N-1 longest gaps as scene boundaries
    inner = [s for s in sil if s["start"] > 0.05 and s["end"] < duration - 0.05]
    cuts = sorted(sorted(inner, key=lambda s: -s["len"])[: a.scenes - 1], key=lambda s: s["start"])
    lead = next((s["end"] for s in sil if s["start"] <= 0.05), 0.0)
    scenes, cur = [], lead
    for c in cuts:
        scenes.append({"start": round(cur, 3), "end": round(c["start"], 3)})
        cur = c["end"]
    tail = next((s["start"] for s in sil if s["end"] >= duration - 0.05), duration)
    scenes.append({"start": round(cur, 3), "end": round(tail, 3)})
    if len(cuts) < a.scenes - 1:
        print("// warning: found fewer pauses than scenes; lower --min or raise --noise")
    print(json.dumps({"duration": round(duration, 3), "scenes": scenes, "silences": sil}, indent=2))


if __name__ == "__main__":
    main()
