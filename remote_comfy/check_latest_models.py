#!/usr/bin/env python3
"""STEP ZERO of any generation workflow: find out what the CURRENT models are.

Why this exists (2026-07-26): a full 3-way image bake-off was run on FLUX.1 Kontext /
Qwen-Image-Edit / FLUX.1-dev+Redux — while **FLUX.2 had been out since Nov 2025** with
native multi-reference (up to 10 images), which was exactly the capability being tested
for. Nobody checked. Standing rule: **always research the latest models BEFORE
designing or running a workflow test.** Assume your training data is stale.

  python check_latest_models.py                 # newest from the usual orgs
  python check_latest_models.py --org Comfy-Org --limit 25
  python check_latest_models.py --search flux   # what FLUX generations exist now

Reads the public HF API (no key). Empirical, not from memory.
"""
import argparse, json, sys, urllib.parse, urllib.request

# Orgs that repackage/publish the models ComfyUI actually loads.
ORGS = ["Comfy-Org", "black-forest-labs", "Qwen", "Wan-AI", "tencent",
        "stabilityai", "Lightricks", "genmo", "rhymes-ai"]
UA = {"User-Agent": "Mozilla/5.0"}


def api(path, **params):
    url = "https://huggingface.co/api/" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read())
    except Exception as e:
        print("  ERR %s: %s" % (path, str(e)[:90]), file=sys.stderr)
        return []


def show(rows, n):
    for m in rows[:n]:
        mid = m.get("id", "?")
        mod = (m.get("lastModified") or "")[:10]
        dl = m.get("downloads", 0) or 0
        print("  %-58s  updated %s  dl %s" % (mid[:58], mod, f"{dl:,}"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", action="append", default=None)
    ap.add_argument("--search", default=None)
    ap.add_argument("--limit", type=int, default=12)
    a = ap.parse_args()

    if a.search:
        print("=== newest matching %r (by lastModified) ===" % a.search)
        show(api("models", search=a.search, sort="lastModified", direction=-1, limit=60), a.limit)
        print("\n=== most downloaded matching %r (what people actually use) ===" % a.search)
        show(api("models", search=a.search, sort="downloads", direction=-1, limit=60), a.limit)
        return 0

    for org in (a.org or ORGS):
        print("=== %s - newest ===" % org)
        show(api("models", author=org, sort="lastModified", direction=-1, limit=40), a.limit)
        print()
    print("REMINDER: newest != best. Check licence (open weights vs API-only), VRAM/file "
          "size (HF api ?blobs=true), whether ComfyUI has native nodes, and whether a Turbo/\n"
          "distilled LoRA exists before committing to a batch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
