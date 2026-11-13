"""Estimate per-phrase and per-word timings for a voiceover, from the clean script.

Builds on scene_times.py: scenes come from the paragraph breaks, then inside each scene the
phrases (split at . , ? ! … : ;) are matched to the short pauses in the audio, and each
phrase's words are spread over it in proportion to their length. Accurate to roughly a
word or two, which is enough for word-highlight captions and for landing animation beats
on a spoken word.

usage: python3 tools/word_times.py voice.mp3 episodes/NNN-slug/clean.txt
  writes episodes/NNN-slug/timing.json and timing.js (window.TIMING, loaded by index.html)
  next to clean.txt, and prints the scenes so you can check them against the take.
output: {"duration", "scenes": [{"start","end","text"}], "phrases": [{"scene","start","end","text","words":[{"w","t0","t1"}]}]}
"""
import json, re, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
import scene_times as st


def split_phrases(par):
    # split after sentence or clause punctuation, keeping the punctuation with the phrase
    parts = re.split(r"(?<=[.!?…,:;])\s+", par.strip())
    return [p for p in parts if p]


def align_inside(pauses, phrases, a, b):
    """Pick len(phrases)-1 pauses inside [a, b] for the phrase breaks (same idea as scene alignment)."""
    if len(phrases) == 1:
        return []
    inner = [s for s in pauses if a + 0.05 < s["start"] and s["end"] < b - 0.05]
    picks = st.pick_aligned(inner, phrases, a, b) if len(inner) >= len(phrases) - 1 else None
    if picks is None:  # not enough pauses: split by character share, no gap
        total = sum(len(p) for p in phrases)
        acc, out = 0, []
        for p in phrases[:-1]:
            acc += len(p)
            t = a + (b - a) * acc / total
            out.append({"start": t, "end": t, "len": 0})
        return out
    return picks


def main():
    mp3, script = sys.argv[1], sys.argv[2]
    duration, sil = st.detect(mp3, -35, 0.12)
    lead, tail = st.speech_bounds(sil, duration)
    paras = st.read_paragraphs(script)
    long_sil = [s for s in sil if s["len"] >= 0.3 and s["start"] > lead and s["end"] < tail]
    cuts = st.pick_aligned(long_sil, paras, lead, tail) or st.pick_longest(long_sil, len(paras) - 1)
    bounds, cur = [], lead
    for c in cuts:
        bounds.append((cur, c["start"])); cur = c["end"]
    bounds.append((cur, tail))

    scenes, phrases = [], []
    for si, ((a, b), par) in enumerate(zip(bounds, paras)):
        scenes.append({"start": round(a, 3), "end": round(b, 3), "text": par})
        ph = split_phrases(par)
        brk = align_inside(sil, ph, a, b)
        pa = a
        for k, p in enumerate(ph):
            pe = brk[k]["start"] if k < len(brk) else b
            words = p.split()
            wl = [len(w) + 1 for w in words]
            tot, acc, ws = sum(wl), 0, []
            for w, l in zip(words, wl):
                t0 = pa + (pe - pa) * acc / tot
                acc += l
                ws.append({"w": w, "t0": round(t0, 3), "t1": round(pa + (pe - pa) * acc / tot, 3)})
            phrases.append({"scene": si, "start": round(pa, 3), "end": round(pe, 3), "text": p, "words": ws})
            pa = brk[k]["end"] if k < len(brk) else b
    data = {"duration": round(duration, 3), "scenes": scenes, "phrases": phrases}
    out = __import__("os").path.dirname(__import__("os").path.abspath(script))
    txt = json.dumps(data, indent=1, ensure_ascii=False)
    open(f"{out}/timing.json", "w").write(txt + "\n")
    open(f"{out}/timing.js", "w").write("window.TIMING = " + json.dumps(data, ensure_ascii=False) + ";\n")
    for i, sc in enumerate(scenes):
        print(f"scene {i + 1}  {sc['start']:6.2f}-{sc['end']:6.2f}  {sc['text'][:70]}")
    print(f"voice ends {duration:.2f} s -> wrote {out}/timing.json and timing.js")


if __name__ == "__main__":
    main()
