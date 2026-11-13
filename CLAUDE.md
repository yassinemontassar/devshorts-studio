# devshorts-studio

Render studio for **@yassine.montassar**'s system design shorts (TikTok, Reels, YouTube Shorts, LinkedIn).
The channel rules, research process, scripts and house style live in the Claude skills
`dev-shorts`, `devshorts-trend-scout` and `devshorts-episode-pack`. This repo holds the code that makes every video look identical.

## Layout
- `episodes/NNN-slug/index.html`: one episode. Every frame is a pure function of time: the page exposes `window.render(t)`, `window.DURATION` and `window.SFX` (the sound events), and loads `timing.js` (word timings from the voice).
- `episodes/NNN-slug/script.txt`: the ElevenLabs script (tagged + clean), the take's details and the exact render commands for that episode.
- `episodes/001-uber-adaptive-lifo/`: **the reference implementation ("blueprint v2" motion system, approved 2026-11-13)**. Copy its index.html; the comment at the top of its script says what to keep and what to replace. Don't invent new visual language.
- `tools/word_times.py`: scene, phrase and word timings from the voice + clean script → `timing.json` and `timing.js` next to `clean.txt`.
- `tools/scene_times.py`: scene starts only (used by word_times; handy for a quick check).
- `tools/render.py`: stills for review, or the full silent MP4 (1080×1920, 30 fps, H.264).
- `tools/sound.py`: sound design (synthesized SFX on `window.SFX`, a mood bed, ducked under the voice, −14 LUFS) muxed onto the silent render → the final MP4.

## Setup (once per session)
```
npm install                      # fonts: Archivo (variable), IBM Plex Mono
pip install playwright numpy scipy --break-system-packages   # if missing; uses system google-chrome
```

## Making an episode from a voiceover
1. `mkdir episodes/NNN-slug`, where NNN is the number of the episode ID in the "Dev Shorts Studio" pipeline sheet (DS-007 → `episodes/007-figma-sharding`), and copy `episodes/001-uber-adaptive-lifo/index.html` into it.
2. Save the CLEAN script (no [tags], one paragraph per scene, blank line between paragraphs) as `episodes/NNN-slug/clean.txt`, then: `python3 tools/word_times.py voice.mp3 episodes/NNN-slug/clean.txt`. Check each printed scene against what you hear.
3. Rebuild the story in the page (see its top comment): `DURATION` (= voice length + ~3 s end card), layout, the beat-by-beat story with every change landing on a spoken word via `W(scene, "word")`, camera keyframes with `fr(t, top, bottom)`, `HEADS`, source text, big numbers, end-card "Next: …". Captions come from `timing.js` automatically. Give each story event that matters an `sfx()`.
4. Review stills at the busiest moments, the start of every scene and the end card: `python3 tools/render.py stills episodes/NNN-slug/index.html stills 0.6 9 21 36 47 56 66 77 81` and look at them. Fix overlaps, clipping and anything under the headline before the full render.
5. Render the silent video: `python3 tools/render.py video episodes/NNN-slug/index.html out/NNN_silent.mp4 --workers 2`
6. Sound + final MP4: `python3 tools/sound.py episodes/NNN-slug/index.html voice.mp3 out/NNN-slug.mp4 --video out/NNN_silent.mp4 --moods "0:calm,<overload start>:tense,<fix start>:resolved"` (moods: calm, tense, resolved; times in seconds). Write the commands you used into script.txt.
7. Commit the episode folder (index.html, script.txt, clean.txt, timing.json, timing.js; not the MP4) straight to `main` and push. New reusable components go into the episode and, once used twice, get noted here.

## Style guardrails (the full spec is in the devshorts-episode-pack skill)
- Blueprint ink background + drafting grid; colour means state: paper, amber = traffic/fix/hero, red = failure, mint = resolved only.
- Archivo 800 at 112% width for headlines (big for 2.4 s, then settle small at the top), Plex Mono for component names and metrics, Archivo 700 karaoke captions at y 1318 (current word amber, spoken white, upcoming dim), source line at y 1262.
- Content column x 80–950; nothing below y 1536 (platform UI).
- One change per beat, landing on the spoken word. The camera frames the part being talked about (screen band y 340–1250); objects move, they don't just appear. Numbered amber callouts, never text cards. Source line on screen for any real company or number.
- Open on the problem already happening (frame 1 is never empty). Big count-up numbers for results, with the world dimmed behind them.
- Sound: a quiet synthesized SFX on every story event that matters, a mood bed (calm → tense → resolved), always under the voice.
- End card: "Next: …" / "Part N: …", @yassine.montassar, "Full breakdown in bio", then a hard cut.
