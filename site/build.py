"""Build site/index.html from site/template.html and the repo's own data.

    python site/build.py

The catalogue block and the counts come from catalog/catalog.json and docs/traps.md,
so the page cannot drift from the repository. Output: site/index.html (+ page.js,
install.md and fonts/ beside it are served as they are).
"""
import datetime
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

TASKS = [  # order and labels on the page
    ("t2i", "Text to image"), ("image-edit", "Image editing"), ("t2v", "Text to video"),
    ("i2v", "Image to video"), ("v2v", "Video to video"), ("lipsync", "Lip-sync and avatars"),
    ("upscale", "Upscaling"), ("3d", "3D"), ("tts", "Speech"), ("music", "Music"),
    ("sfx", "Sound effects"), ("utility", "Utilities"),
]
LIC = {"True": ("open", "Open"), "conditional": ("", "Terms"), "False": ("nc", "NC")}


def catalog_block(models):
    by = {}
    for m in models:
        by.setdefault(m["task"], []).append(m)
    unknown = set(by) - {t for t, _ in TASKS}
    if unknown:
        raise SystemExit("catalog has tasks the page does not label: %s" % sorted(unknown))
    out = []
    for task, label in TASKS:
        rows = []
        for m in by.get(task, []):
            cls, word = LIC[str(m["commercial_ok"])]
            name = m["name"].split(" (")[0]
            vram = "%s GB" % m["vram_gb"] if m.get("vram_gb") else ""
            rows.append('      <li><span>%s</span><i>%s</i><span class="lic %s">%s</span></li>'
                        % (html.escape(name), vram, cls, word))
        out.append('    <section><h3><span>%s</span><span>%d</span></h3><ul>\n%s\n    </ul></section>'
                   % (html.escape(label), len(rows), "\n".join(rows)))
    return "\n".join(out)


def main():
    cat = json.load(open(os.path.join(REPO, "catalog", "catalog.json"), encoding="utf-8"))
    models = cat["models"]
    tasks = {m["task"] for m in models}
    traps_md = open(os.path.join(REPO, "docs", "traps.md"), encoding="utf-8").read()
    traps = len([l for l in traps_md.splitlines() if l.startswith("| ") and not l.startswith("| trap |")])
    d = datetime.date.fromisoformat(cat["checked_on"])
    checked = "%d %s %d" % (d.day, d.strftime("%B"), d.year)

    page = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    subs = {
        "__CATALOG__": catalog_block(models),
        "__MODELS__": str(len(models)),
        "__TASKS__": str(len(tasks)),
        "__CHECKED__": checked,
        "__TRAPS6__": str(traps).zfill(6),
        "__TRAPS__": str(traps),
    }
    for k, v in subs.items():
        page = page.replace(k, v)
    left = re.findall(r"__[A-Z0-9]+__", page)
    if left:
        raise SystemExit("unfilled placeholders: %s" % sorted(set(left)))
    open(os.path.join(HERE, "index.html"), "w", encoding="utf-8", newline="\n").write(page)
    print("wrote site/index.html: %d models, %d tasks, %d traps, checked %s" % (len(models), len(tasks), traps, checked))


main()
