#!/usr/bin/env python3
"""The model + workflow catalogue: curated pointers to current open models by task.

The catalogue is DATA (catalog/catalog.json), not prose, because model lists rot faster
than anything else in this repo. Every entry carries the date it was checked, and
--verify re-checks every repo and file against the live Hugging Face API.

  python remote_comfy/catalog.py                    # all tasks, best first
  python remote_comfy/catalog.py --task i2v         # one task
  python remote_comfy/catalog.py --validate         # offline schema check (CI runs this)
  python remote_comfy/catalog.py --verify           # live: repos + file paths still exist?
  python remote_comfy/catalog.py --dl wan2.2-i2v-a14b --skip bf16   # extra-models.txt lines
  python remote_comfy/catalog.py --write-docs       # regenerate docs/models.md

The catalogue is a starting point, not a substitute for STEP ZERO: run
check_latest_models.py before committing a batch to any entry.
"""
import argparse, datetime, io, json, os, re, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = os.path.join(ROOT, "catalog", "catalog.json")
UA = {"User-Agent": "Mozilla/5.0"}
STALE_DAYS = 90

TASKS = {  # key -> heading, in display order
    "t2i": "Text to image",
    "image-edit": "Image editing / multi-reference",
    "t2v": "Text to video",
    "i2v": "Image to video",
    "v2v": "Video to video / restyle / extend",
    "lipsync": "Lip-sync / talking head / avatar",
    "upscale": "Upscaling (image and video)",
    "3d": "3D generation",
    "tts": "Speech / voice cloning",
    "music": "Music",
    "sfx": "Sound effects / video-to-audio",
    "utility": "Control and utilities",
}
SUPPORT = ("native", "custom-node", "none")
REQUIRED = ("id", "name", "task", "license", "comfy_support", "pick_when")
REPO_RE = re.compile(r"^[A-Za-z0-9][\w.-]*/[\w.-]+$")
DIR_RE = re.compile(r"^[a-z0-9_]+(/[a-z0-9_]+)?$")


def load(path=DEFAULT):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(cat, today=None):
    """Offline checks. Returns a list of problems; empty means valid."""
    errs = []
    today = today or datetime.date.today()
    try:
        checked = datetime.date.fromisoformat(cat.get("checked_on", ""))
        if (today - checked).days > STALE_DAYS:
            errs.append("catalogue checked_on %s is over %d days old: re-run --verify and "
                        "re-research" % (checked, STALE_DAYS))
    except ValueError:
        errs.append("checked_on must be YYYY-MM-DD")
    seen = set()
    for i, m in enumerate(cat.get("models", [])):
        tag = m.get("id") or "#%d" % i
        for k in REQUIRED:
            if not m.get(k):
                errs.append("%s: missing %s" % (tag, k))
        if not (m.get("hf_repo") or m.get("comfy_repo")):
            errs.append("%s: needs hf_repo (upstream) or comfy_repo (repackaged)" % tag)
        if m.get("commercial_ok") not in (True, False, "conditional", None):
            errs.append("%s: commercial_ok must be true, false or 'conditional'" % tag)
        if m.get("id") in seen:
            errs.append("%s: duplicate id" % tag)
        seen.add(m.get("id"))
        if m.get("task") not in TASKS:
            errs.append("%s: unknown task %r" % (tag, m.get("task")))
        if m.get("comfy_support") not in SUPPORT:
            errs.append("%s: comfy_support must be one of %s" % (tag, SUPPORT))
        if m.get("comfy_support") == "custom-node" and not m.get("custom_node_repo"):
            errs.append("%s: custom-node support needs custom_node_repo" % tag)
        for k in ("hf_repo", "comfy_repo"):
            if m.get(k) and not REPO_RE.match(m[k]):
                errs.append("%s: %s is not an owner/name repo id" % (tag, k))
        for u in ("workflow_url", "custom_node_repo"):
            if m.get(u) and not m[u].startswith("https://"):
                errs.append("%s: %s must be an https URL" % (tag, u))
        for f in m.get("files") or []:
            # comfy_dir null = a custom node fetches this file itself (listed for size only)
            node_fetched = f.get("comfy_dir") is None and m.get("comfy_support") == "custom-node"
            if not (f.get("repo") and f.get("path") and (f.get("comfy_dir") or node_fetched)):
                errs.append("%s: each file needs repo, path, comfy_dir (null only for custom-node)" % tag)
            elif ".." in f["path"] or f["path"].startswith("/") or (
                    f.get("comfy_dir") and not DIR_RE.match(f["comfy_dir"])):
                errs.append("%s: unsafe path/comfy_dir %s -> %s" % (tag, f["path"], f["comfy_dir"]))
    for w in cat.get("workflows", []):
        if not (w.get("name") and str(w.get("url", "")).startswith("https://")):
            errs.append("workflow %r needs a name and an https url" % w.get("name"))
    return errs


def hf_model(repo):
    """Live HF metadata incl. file list, or None if the repo is gone/unreachable."""
    url = "https://huggingface.co/api/models/%s?blobs=true" % urllib.parse.quote(repo, safe="/")
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                                 timeout=45).read())
    except Exception:
        return None


def verify(cat, fetch=hf_model):
    """Live checks: every repo resolves and every listed file is still at its path."""
    probs, cache = [], {}

    def get(repo):
        if repo not in cache:
            cache[repo] = fetch(repo)
        return cache[repo]
    for m in cat.get("models", []):
        for k in ("hf_repo", "comfy_repo"):
            if m.get(k) and get(m[k]) is None:
                probs.append("%s: %s %s not found" % (m["id"], k, m[k]))
        for f in m.get("files") or []:
            info = get(f["repo"])
            if info is None:
                continue  # already reported above, or reported once here
            names = {s.get("rfilename") for s in info.get("siblings", [])}
            if f["path"] not in names:
                probs.append("%s: file moved or gone: %s/%s" % (m["id"], f["repo"], f["path"]))
    return probs


def dl_lines(cat, ids, skip=()):
    """`<repo> <path> models/<dir>` lines that provision-comfyui.sh reads from
    /workspace/extra-models.txt. `skip` drops paths containing any of these substrings,
    e.g. ["bf16"] when an entry lists several precisions of the same weights. Exclusion,
    not inclusion: a keep-filter like "int8" silently drops shared files (VAEs, encoders)
    whose names carry no precision tag."""
    by_id = {m["id"]: m for m in cat.get("models", [])}
    out = []
    for i in ids:
        if i not in by_id:
            raise KeyError("no catalogue entry %r" % i)
        if not by_id[i].get("files"):
            raise KeyError("%r lists no files (custom-node install, or not ComfyUI-ready)" % i)
        fs = [f for f in by_id[i]["files"] if not any(x in f["path"] for x in skip)]
        if not any(f.get("comfy_dir") for f in fs):
            raise KeyError("%r: its custom node (%s) downloads these weights itself; install the "
                           "node instead" % (i, by_id[i].get("custom_node_repo")))
        out += ["%s %s models/%s" % (f["repo"], f["path"], f["comfy_dir"]) for f in fs if f.get("comfy_dir")]
    return out


def _size(m):
    tot = sum(f.get("size_gb") or 0 for f in m.get("files") or [])
    return ("%.0f GB" % tot) if tot else "-"


def markdown(cat):
    L = ["# Model catalogue", "",
         "Generated from `catalog/catalog.json` by `python remote_comfy/catalog.py --write-docs`.",
         "Do not edit by hand: a test fails if this file and the JSON disagree.", "",
         "Checked against Hugging Face on **%s**. Model lists rot fast: run" % cat["checked_on"],
         "`python remote_comfy/catalog.py --verify` and STEP ZERO "
         "(`check_latest_models.py`) before committing a batch.", ""]
    for key, head in TASKS.items():
        ms = [m for m in cat["models"] if m["task"] == key]
        if not ms:
            continue
        L += ["## %s" % head, "", "| model | licence | ComfyUI | VRAM | files | pick when |",
              "|---|---|---|---|---|---|"]
        for m in ms:
            name = "[%s](https://huggingface.co/%s)" % (m["name"], m.get("hf_repo") or m["comfy_repo"])
            sup = m["comfy_support"]
            if m.get("custom_node_repo"):
                sup = "[%s](%s)" % (sup, m["custom_node_repo"])
            if m.get("workflow_url"):
                sup += " · [workflow](%s)" % m["workflow_url"]
            lic = m["license"] + {False: " (non-commercial)", "conditional": " (conditional)"}.get(
                m.get("commercial_ok"), "")
            vram = ("%s GB" % m["vram_gb"]) if m.get("vram_gb") else "-"
            L.append("| %s `%s` | %s | %s | %s | %s | %s |" % (
                name, m["id"], lic, sup, vram, _size(m), m["pick_when"].replace("|", "/")))
        L.append("")
    if cat.get("workflows"):
        L += ["## Workflow sources and techniques", ""]
        L += ["- [%s](%s): %s" % (w["name"], w["url"], w.get("note", "")) for w in cat["workflows"]]
        L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=DEFAULT)
    ap.add_argument("--task", choices=sorted(TASKS))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--validate", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--write-docs", action="store_true",
                   help="regenerate docs/models.md (written as UTF-8/LF, never via a shell redirect)")
    g.add_argument("--dl", nargs="+", metavar="ID")
    ap.add_argument("--skip", action="append", default=[], metavar="SUBSTR",
                    help="with --dl: drop file paths containing this (repeatable), e.g. bf16")
    a = ap.parse_args(argv)
    cat = load(a.catalog)

    if a.validate:
        errs = validate(cat)
        print("\n".join(errs) or "catalog OK: %d models, %d workflows" % (
            len(cat["models"]), len(cat.get("workflows", []))))
        return 1 if errs else 0
    if a.verify:
        probs = verify(cat)
        print("\n".join(probs) or "all repos and file paths resolve on Hugging Face")
        return 1 if probs else 0
    if a.write_docs:
        # Written here, not via `> docs/models.md`: a Windows shell redirect re-encodes to
        # cp1252 and CRLF, and the doc-sync test then fails on a non-UTF-8 byte.
        out = os.path.join(ROOT, "docs", "models.md")
        io.open(out, "w", encoding="utf-8", newline="\n").write(markdown(cat))
        print("wrote %s" % out)
        return 0
    if a.dl:
        try:
            print("\n".join(dl_lines(cat, a.dl, a.skip)))
        except KeyError as e:
            sys.exit("catalog --dl: %s" % e.args[0])
        return 0
    for key, head in TASKS.items():
        if a.task and key != a.task:
            continue
        ms = [m for m in cat["models"] if m["task"] == key]
        if ms:
            print("== %s" % head)
            for m in ms:
                print("  %-22s %-34s %-12s %s" % (m["id"], (m.get("hf_repo") or m["comfy_repo"])[:34],
                                                 m["comfy_support"],
                                                 m["pick_when"][:70]))
    print("\nchecked_on %s - run --verify before relying on it" % cat["checked_on"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
