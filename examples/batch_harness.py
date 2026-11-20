#!/usr/bin/env python3
"""Shard-aware batch harness: the contract `pod/launch-sharded.sh` expects.

  python3 -u batch_harness.py --comfy http://127.0.0.1:8188 --shard 0 --of 1 \
      --jobs jobs.json --out /workspace/out
  python3 -u batch_harness.py --comfy cloud --inputs ./inputs --jobs jobs.json --out ./out

jobs.json is a list of {"id", "workflow": <API-format JSON path, relative to jobs.json>,
"set": {"<node>.<input>": value}}. Shard N takes every job whose index % M == N.
A job is SKIPPED when any file named <id>_* already exists in --out, so a relaunch
resumes instead of redoing. Move --out aside before re-running with new settings
(see the dedupe caveat in local/sync-outputs.sh).

--inputs DIR uploads every `set` value that names a file in DIR (once each) and sets what
the server returned in its place: needed on Comfy Cloud, where there is no disk to scp to.

Runs on the pod beside comfy_client.py, or from a repo checkout.
"""
import argparse, copy, glob, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "remote_comfy"), "/workspace"]
from comfy_client import connect  # noqa: E402


def apply(workflow, sets):
    wf = copy.deepcopy(workflow)
    for key, val in sets.items():
        node, field = key.split(".", 1)
        if node not in wf:
            raise KeyError("job sets %s but the workflow has no node %s" % (key, node))
        wf[node]["inputs"][field] = val
    return wf


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--comfy", default="http://127.0.0.1:8188")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wait-min", type=float, default=30)
    ap.add_argument("--inputs", default=None, help="upload set values naming files in this dir")
    a = ap.parse_args(argv)

    jobs = json.load(open(a.jobs))
    base = os.path.dirname(os.path.abspath(a.jobs))
    mine = [j for i, j in enumerate(jobs) if i % a.of == a.shard]
    os.makedirs(a.out, exist_ok=True)
    todo = [j for j in mine if not glob.glob(os.path.join(a.out, j["id"] + "_*"))]
    print("shard %d/%d: %d jobs, %d already on disk" % (a.shard, a.of, len(mine), len(mine) - len(todo)))
    if not todo:
        return 0

    c = connect(a.comfy)
    c.wait_ready()
    cache, uploaded, fails = {}, {}, 0
    for j in todo:
        path = os.path.join(base, j["workflow"])
        sets = dict(j.get("set", {}))
        for k, v in sets.items():
            f = os.path.join(a.inputs, v) if a.inputs and isinstance(v, str) else None
            if f and os.path.isfile(f):
                if v not in uploaded:
                    uploaded[v] = c.upload(f)
                sets[k] = uploaded[v]
        wf = apply(cache.setdefault(path, json.load(open(path))), sets)
        t0 = time.time()
        try:
            outs = c.run(wf, wait_min=a.wait_min)
        except Exception as e:                      # keep going; the count below is the truth
            fails += 1
            print("FAIL %s: %s" % (j["id"], str(e)[:300]))
            continue
        for name, data in outs:
            open(os.path.join(a.out, "%s_%s" % (j["id"], name)), "wb").write(data)
        print("ok %s  %d file(s)  %.1fs" % (j["id"], len(outs), time.time() - t0))
    print("shard %d done: %d ok, %d failed" % (a.shard, len(todo) - fails, fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
