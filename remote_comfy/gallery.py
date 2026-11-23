#!/usr/bin/env python3
"""Make one page that shows a run's outputs: images, video and audio in place, other files listed.

    python remote_comfy/gallery.py ./out [more folders or files] [--html PATH] [--title TEXT]

Writes gallery.html beside the first folder (or at --html) and prints its path. The page
links each file by a relative path, so it works opened from disk and moves with its
folder. It is for opening a batch in a browser; to show outputs in a Claude app, send the
files themselves. Stdlib only.
"""
import argparse
import html
import os
import pathlib
import sys
import urllib.parse

IMAGE = (".png", ".jpg", ".jpeg", ".webp", ".gif")
VIDEO = (".mp4", ".webm", ".mov")
AUDIO = (".wav", ".mp3", ".flac", ".ogg", ".m4a")
OTHER = (".glb", ".gltf", ".obj", ".ply", ".fbx", ".exr", ".tif", ".tiff")
NAME = "gallery.html"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<style>
:root { color-scheme: light dark; --bg: #f4f2ee; --ink: #1b1b1b; --dim: #6b6b6b; --card: #ffffff; }
@media (prefers-color-scheme: dark) { :root { --bg: #141414; --ink: #ececec; --dim: #9a9a9a; --card: #1e1e1e; } }
body { margin: 0; padding: 16px; background: var(--bg); color: var(--ink); font: 14px/1.4 system-ui, sans-serif; }
h1 { font-size: 16px; margin: 0 0 4px; }
p.sum { color: var(--dim); margin: 0 0 16px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
figure { margin: 0; background: var(--card); border-radius: 6px; overflow: hidden; }
figure img, figure video { display: block; width: 100%%; height: auto; background: #000; }
figure img { background: repeating-conic-gradient(#8a8a8a 0 25%%, #b0b0b0 0 50%%) 50%% / 16px 16px; }
figure audio { display: block; width: 100%%; margin: 12px 0 0; }
figcaption { padding: 6px 8px; font: 12px/1.3 ui-monospace, monospace; word-break: break-all; }
figcaption span { color: var(--dim); }
ul.other { font: 12px/1.6 ui-monospace, monospace; padding-left: 18px; }
a { color: inherit; }
</style></head><body>
<h1>%(title)s</h1>
<p class="sum">%(summary)s</p>
<div class="grid">
%(cards)s
</div>
%(other)s
</body></html>
"""


def _size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def _collect(paths, skip):
    found = []
    for p in paths:
        if os.path.isfile(p):
            found.append(os.path.abspath(p))
            continue
        for d, dirs, names in os.walk(p):
            dirs[:] = sorted(x for x in dirs if not x.startswith("."))
            for n in sorted(names):
                full = os.path.abspath(os.path.join(d, n))
                if not n.startswith(".") and full != skip:
                    found.append(full)
    return [f for f in found if f.lower().endswith(IMAGE + VIDEO + AUDIO + OTHER)]


def _href(target, page_dir):
    try:
        rel = os.path.relpath(target, page_dir).replace(os.sep, "/")
    except ValueError:  # another drive on Windows: no relative path exists
        return pathlib.Path(target).as_uri()
    return urllib.parse.quote(rel)


def build(paths, html_path=None, title=None):
    """Write the page and return its path. Raises SystemExit if there is nothing to show."""
    first = paths[0] if os.path.isdir(paths[0]) else os.path.dirname(os.path.abspath(paths[0]))
    html_path = os.path.abspath(html_path or os.path.join(first, NAME))
    files = _collect(paths, skip=html_path)
    if not files:
        raise SystemExit("gallery: no images, video, audio or 3D files in %s" % ", ".join(paths))
    page_dir = os.path.dirname(html_path)
    cards, other = [], []
    for f in files:
        url = html.escape(_href(f, page_dir), quote=True)
        label = html.escape(os.path.relpath(f, first).replace(os.sep, "/") if f.startswith(os.path.abspath(first)) else os.path.basename(f))
        cap = "<figcaption>%s <span>%s</span></figcaption>" % (label, _size(os.path.getsize(f)))
        low = f.lower()
        if low.endswith(IMAGE):
            cards.append('<figure><a href="%s"><img src="%s" alt="%s" loading="lazy"></a>%s</figure>' % (url, url, label, cap))
        elif low.endswith(VIDEO):
            cards.append('<figure><video src="%s" controls loop muted playsinline preload="metadata"></video>%s</figure>' % (url, cap))
        elif low.endswith(AUDIO):
            cards.append('<figure><audio src="%s" controls preload="metadata"></audio>%s</figure>' % (url, cap))
        else:
            other.append('<li><a href="%s">%s</a> %s</li>' % (url, label, _size(os.path.getsize(f))))
    summary = "%d file(s) from %s" % (len(files), html.escape(", ".join(os.path.basename(os.path.abspath(p)) for p in paths)))
    page = PAGE % {
        "title": html.escape(title or "Outputs"),
        "summary": summary,
        "cards": "\n".join(cards),
        "other": ("<h1>Other files</h1>\n<ul class=\"other\">%s</ul>" % "".join(other)) if other else "",
    }
    with open(html_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    return html_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", help="output folders or files")
    ap.add_argument("--html", help="where to write the page (default: gallery.html in the first folder)")
    ap.add_argument("--title", help="page title")
    a = ap.parse_args(argv)
    print(build(a.paths, a.html, a.title))
    return 0


if __name__ == "__main__":
    sys.exit(main())
