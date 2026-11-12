# devshorts-studio

Render studio for **@yassine.montassar**'s system design shorts (TikTok, Reels, YouTube Shorts, LinkedIn).
The channel rules, research process, scripts and house style live in the Claude skills
`dev-shorts`, `devshorts-trend-scout` and `devshorts-episode-pack`. This repo holds the code that makes every video look identical.

## Layout
- `episodes/NNN-slug/index.html`: one episode. Every frame is a pure function of time: the page exposes `window.render(t)` and `window.DURATION`.
- `episodes/NNN-slug/script.txt`: the ElevenLabs script (tagged + clean) for that episode.
- `episodes/000-reference/`: **the reference implementation** of the "engineer's blueprint" style (the pilot "Your cache just died"; never posted). Copy its structure, CSS, helpers and components; don't invent new visual language. Real episodes start at 001.
- `tools/scene_times.py`: finds scene starts in the voiceover (the longest pauses = paragraph breaks).
- `tools/render.py`: renders stills for review, or the full MP4 (1080×1920, 30 fps, H.264), with the MP3 muxed in.

## Setup (once per session)
```
npm install                      # fonts: Archivo (variable), IBM Plex Mono
pip install playwright --break-system-packages   # if missing; uses system google-chrome
```

## Making an episode from a voiceover
1. `mkdir episodes/NNN-slug` (next free number from 001) and copy `episodes/000-reference/index.html` into it.
2. Scene timing from the voice: `python3 tools/scene_times.py voice.mp3 --scenes <paragraph count>`
3. Edit only the data at the top of the page: `DURATION` (= MP3 length + ~3 s end card), `TITLES`, `CAPTIONS` (from the CLEAN script; split each scene's phrases across its span in proportion to their length), and the story-state functions (`redisMode`, `pgLoad`, ...) so every visual change lands on its scene start. Replace the diagram nodes for the new system using the same components.
4. Review stills at the busiest moments: `python3 tools/render.py stills episodes/NNN-slug/index.html stills 2 9 14 21 32 44 48` and look at them.
5. Render: `python3 tools/render.py video episodes/NNN-slug/index.html out/NNN-slug.mp4 --workers 2 --audio voice.mp3`
6. Commit the episode folder (not the MP4). New reusable components go into the episode and, once used twice, get noted here.

## Style guardrails (the full spec is in the devshorts-episode-pack skill)
- Blueprint ink background + drafting grid; colour means state: paper, amber = traffic/fix/hero, red = failure, mint = resolved only.
- Archivo 800 at 112% width for headlines, Plex Mono for component names and metrics, Archivo 600 captions at y 1408.
- Content column x 80–950; nothing below y 1536 (platform UI).
- One change per beat. Pen-drawn diagrams, numbered amber callouts, never text cards. Source line on screen for any real company or number.
- End card: "Next: …" / "Part N: …", @yassine.montassar, "Full breakdown in bio", then a hard cut.
