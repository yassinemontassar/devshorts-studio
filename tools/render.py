"""Render a dev-shorts HTML composition to MP4, frame by frame.

usage:
  python3 render.py stills <html> <out_dir> t1 t2 ... [--platform P]   # PNG stills for review
  python3 render.py video  <html> <out.mp4> [--workers 4] [--audio a.mp3] [--platform P]
  python3 render.py endcards <html> <final.mp4> [--platforms tiktok,instagram,youtube,linkedin]
      re-renders only the end card for each platform (its handle) and writes <final>-<platform>.mp4,
      keeping the video before window.ENDCARD_T and the audio of <final.mp4>.
The page must expose window.render(t) and window.DURATION; the platform is passed as ?p=<platform>.
"""
import asyncio, os, subprocess, sys, pathlib, shutil
from playwright.async_api import async_playwright

FPS = 30
W, H = 1080, 1920


PLATFORM = None


async def open_page(pw, html):
    browser = await pw.chromium.launch(executable_path=shutil.which("google-chrome"), args=["--force-color-profile=srgb", "--disable-lcd-text"])
    page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    await page.goto(pathlib.Path(html).resolve().as_uri() + (f"?p={PLATFORM}" if PLATFORM else ""))
    await page.evaluate("document.fonts.ready")
    await page.wait_for_timeout(300)
    return browser, page


async def stills(html, out_dir, times):
    os.makedirs(out_dir, exist_ok=True)
    async with async_playwright() as pw:
        browser, page = await open_page(pw, html)
        for t in times:
            await page.evaluate(f"window.render({t})")
            await page.screenshot(path=f"{out_dir}/t{float(t):05.1f}.png", clip={"x": 0, "y": 0, "width": W, "height": H})
        await browser.close()


async def render_range(html, f0, f1, out):
    tmp = out.replace(".mp4", ".part.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp], stdin=subprocess.PIPE)
    async with async_playwright() as pw:
        browser, page = await open_page(pw, html)
        for f in range(f0, f1):
            await page.evaluate(f"window.render({f / FPS})")
            ff.stdin.write(await page.screenshot(type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": W, "height": H}))
        await browser.close()
    ff.stdin.close()
    if ff.wait() == 0:
        os.replace(tmp, out)
    else:
        raise SystemExit(f"ffmpeg failed on {out}")


async def video(html, out, workers=4, audio=None):
    async with async_playwright() as pw:
        browser, page = await open_page(pw, html)
        dur = await page.evaluate("window.DURATION")
        await browser.close()
    total = round(dur * FPS)
    chunk = -(-total // workers)
    work = pathlib.Path(out).with_suffix("")
    work.mkdir(parents=True, exist_ok=True)
    parts = [str(work / f"part{i}.mp4") for i in range(workers)]
    await asyncio.gather(*[render_range(html, i * chunk, min(total, (i + 1) * chunk), parts[i]) for i in range(workers) if i * chunk < total])
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{os.path.abspath(p)}'\n" for p in parts if os.path.exists(p)))
    silent = str(work / "silent.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", silent], check=True)
    if audio:
        # apad pads the voice with silence so the end card (after the voice ends) is kept; -shortest then cuts at the video's end
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-af", "apad", "-c:a", "aac", "-b:a", "192k", "-shortest", out], check=True)
    else:
        os.replace(silent, out)
    print("wrote", out, f"{total} frames")


async def endcards(html, final, platforms):
    global PLATFORM
    async with async_playwright() as pw:
        browser, page = await open_page(pw, html)
        dur, t0 = await page.evaluate("[window.DURATION, window.ENDCARD_T]")
        await browser.close()
    f0, total = int(t0 * FPS), round(dur * FPS)
    base = str(pathlib.Path(final).with_suffix(""))
    for p in platforms:
        PLATFORM = p
        tail = f"{base}-{p}.tail.mp4"
        await render_range(html, f0, total, tail)
        tmp = f"{base}-{p}.part.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", final, "-i", tail, "-filter_complex",
                        f"[0:v]trim=end_frame={f0},setpts=PTS-STARTPTS[a];[a][1:v]concat=n=2:v=1:a=0[v]",
                        "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-r", str(FPS), "-c:a", "copy", "-shortest", tmp], check=True)
        os.replace(tmp, f"{base}-{p}.mp4"); os.remove(tail)
        print("wrote", f"{base}-{p}.mp4")


if __name__ == "__main__":
    mode = sys.argv[1]
    argv = sys.argv[2:]
    if "--platform" in argv:
        i = argv.index("--platform"); PLATFORM = argv[i + 1]; del argv[i:i + 2]
    sys.argv = sys.argv[:2] + argv
    if mode == "stills":
        asyncio.run(stills(sys.argv[2], sys.argv[3], [float(x) for x in sys.argv[4:]]))
    elif mode == "endcards":
        a = sys.argv[2:]
        plats = a[a.index("--platforms") + 1].split(",") if "--platforms" in a else ["tiktok", "instagram", "youtube", "linkedin"]
        asyncio.run(endcards(a[0], a[1], plats))
    else:
        args = sys.argv[2:]
        workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 4
        audio = args[args.index("--audio") + 1] if "--audio" in args else None
        asyncio.run(video(args[0], args[1], workers, audio))
