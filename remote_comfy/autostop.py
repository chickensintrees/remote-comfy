#!/usr/bin/env python3
"""Idle watchdog that runs ON the pod and STOPS THE POD ITSELF when work is done.

Why on-pod and not local: a local watchdog dies with the laptop/session/agent, and a
forgotten pod bills 24/7 ($0.44/hr = $10/day). This one lives on the machine it kills,
so an abandoned pod still shuts itself off. Belt-and-braces with `pod_ctl.py watch`.

  # on the pod (RUNPOD_API_KEY in env, never written to disk):
  # key on ssh stdin, never a command line:
  ... | ssh ... 'read -r K; RUNPOD_API_KEY=$K nohup setsid python3 /workspace/autostop.py \
      --pod-id <podId> --idle-min 15 > /workspace/autostop.log 2>&1 </dev/null & disown'

Idle = ComfyUI /queue has nothing running AND nothing pending, continuously, for
--idle-min. Any queued job resets the clock.

LOCKFILE: while /workspace/.busy exists the watchdog never stops the pod. Long
non-ComfyUI work (a 24GB model download, an rsync) must `touch /workspace/.busy`
first and remove it after, or it will be killed mid-flight.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

LOCK = "/workspace/.busy"
# RunPod REST v2. REST v1 was retired on 2026-11-15 (its host no longer resolves) and
# GraphQL is deprecated (retires early 2027), so the watchdog uses v2 only.
RP = "https://api.runpod.io/v2"
# Cloudflare answered 403/1010 to urllib's default User-Agent on the old APIs. EVERY RunPod
# call goes through _runpod() with a browser UA: on 2026-10-23 the stock check, stop and
# terminate all 403'd while only one call carried it, so the watchdog could never retire
# the pod it was guarding.
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"


def _runpod(url, key, method="GET", body=None, timeout=30):
    # strip(): a key piped from Windows Python arrives as "key\r"; the CR made every call
    # raise "Invalid header value" and the watchdog could never act (2026-11-20).
    req = urllib.request.Request(url, method=method,
                                 data=(json.dumps(body).encode() if body is not None else
                                       (b"" if method == "POST" else None)),
                                 headers={"Authorization": "Bearer " + key.strip(),
                                          "Content-Type": "application/json",
                                          "User-Agent": BROWSER_UA})
    return urllib.request.urlopen(req, timeout=timeout).read()


SECRETS = []   # filled by main(); never printed


def log(msg):
    """Every line goes through here, scrubbed: urllib's "Invalid header value" error quotes
    the whole Authorization header, which once put the API key in the pod's log (2026-11-20)."""
    msg = re.sub(r"Bearer\s+\S+", "Bearer ***", str(msg))
    for s in SECRETS:
        if s:
            msg = msg.replace(s, "***")
    print("%s %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def comfy_busy(comfy, timeout=10):
    """True=busy, False=idle, None=unreachable (don't count as idle: it may be booting)."""
    try:
        with urllib.request.urlopen(comfy.rstrip("/") + "/queue", timeout=timeout) as r:
            q = json.loads(r.read())
        return bool(q.get("queue_running") or q.get("queue_pending"))
    except Exception:
        return None


def stop_pod(pod_id, key, dry):
    if dry:
        log("DRY-RUN: would stop pod %s now" % pod_id)
        return True
    for attempt in range(5):
        try:
            _runpod("%s/pods/%s/action" % (RP, pod_id), key, method="POST", body={"action": "stop"})
            log("STOPPED pod %s" % pod_id)
            return True
        except urllib.error.HTTPError as e:
            log("stop failed HTTP %s: %s" % (e.code, e.read().decode(errors="replace")[:120]))
        except Exception as e:
            log("stop error: %s" % str(e)[:120])
        time.sleep(5 * (attempt + 1))
    return False


SYNCED = "/workspace/.synced"       # touched by sync-outputs.sh after each successful pull


def lock_held(ttl_min):
    """Is /workspace/.busy present AND FRESH?

    THE LOCK IS A HEARTBEAT, NOT A FLAG (2026-07-27, cost ~3h of idle H100 = ~$9).
    A sweep script touched .busy, finished, and exited without removing it. The watchdog
    dutifully "held" a completely idle pod for three hours. A lock that outlives the job
    holding it is indistinguishable from a lock nobody cleaned up — so it must EXPIRE:
    long jobs re-touch it while they run (see hold-busy.sh), and a forgotten one goes
    stale on its own. Never trust mere existence.
    """
    try:
        age = time.time() - os.path.getmtime(LOCK)
    except OSError:
        return False, None
    return age < ttl_min * 60, age


def gpu_stock(pod_id, key):
    """Stock status for THIS pod's GPU type, or None if it cannot be determined.

    This is the whole fix for stranded pods. `stop` hands the GPU back to the host pool;
    `start` then needs free GPUs ON THAT HOST. Stopping while stock is thin means the host
    refills and the pod can never restart — and everything on its pod-local volume
    (50GB of model weights, in our case) becomes unreachable while still billing storage.
    A stop is only a PAUSE when the card is easy to get back.

    Returns "High", "Medium", "Low" or "None" (v2's HIGH/MEDIUM/LOW/NONE, title-cased), read
    for this pod's data centre when the catalogue lists it, since a restart needs a GPU
    there, not anywhere.
    """
    try:
        pod = json.loads(_runpod("%s/pods/%s" % (RP, pod_id), key, timeout=20))
        gpu = pod.get("gpu") or {}
        want = gpu.get("id")
        if not want:
            return None
        q = urllib.parse.urlencode({"include": "AVAILABILITY", "product": "POD",
                                    "count": gpu.get("count") or 1, "cloud": pod.get("cloud") or "SECURE"})
        gpus = json.loads(_runpod("%s/catalog/gpus?%s" % (RP, q), key, timeout=20)).get("gpus") or []
        for t in gpus:
            if t.get("id") == want:
                here = [d.get("availability") for d in (t.get("dataCenters") or [])
                        if d.get("id") == pod.get("dataCenterId")]
                level = (here[0] if here else t.get("availability")) or ""
                return level.title() or None
    except Exception as e:
        log("stock check failed: %s" % str(e)[:100])
    return None


def terminate_pod(pod_id, key, dry):
    """True only if RunPod accepted the terminate. A failure must reach the caller: the
    watchdog used to log it and exit, leaving the pod billing unguarded (2026-10-23)."""
    if dry:
        log("DRY-RUN: would TERMINATE pod %s now" % pod_id); return True
    for attempt in range(3):
        try:
            _runpod("%s/pods/%s" % (RP, pod_id), key, method="DELETE", timeout=45)
            log("TERMINATED pod %s (billing stops; pod-local disk destroyed)" % pod_id)
            return True
        except Exception as e:
            log("terminate error: %s" % str(e)[:120])
        time.sleep(5 * (attempt + 1))
    return False


SYNCED_D = "/workspace/.synced.d"   # per-directory sentinels: one file per synced remote dir


def _slug(path):
    return "".join(ch if ch.isalnum() else "_" for ch in path)


def unsynced_dirs(roots, max_age_min=15.0):
    """Output dirs written recently that have NO fresh sentinel — i.e. work that exists
    only on this pod.

    WHY PER-DIRECTORY (2026-07-27): a single global
    /workspace/.synced meant ANY running sync loop asserted that ALL outputs were safe.
    The terminate-rather-than-strand branch trusts that signal, so it could have destroyed
    a pod still holding unsynced frames from a different directory. The evidence was
    weaker than the decision resting on it.

    Returns a list of directory paths that look unsafe to destroy.
    """
    bad = []
    now = time.time()
    for root in roots:
        root = root.rstrip("/") or "/"
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            continue
        # The root ITSELF is an output dir when files sit directly in it. Checking only its
        # subdirectories let a flat /workspace/out read as "synced" with nothing checked.
        cands = [root] if any(os.path.isfile(os.path.join(root, n)) for n in entries) else []
        cands += [os.path.join(root, n) for n in entries if os.path.isdir(os.path.join(root, n))]
        for d in cands:
            try:
                newest = max((os.path.getmtime(os.path.join(d, f)) for f in os.listdir(d)
                              if os.path.isfile(os.path.join(d, f))), default=0)
            except OSError:
                continue
            if newest == 0:
                continue                                   # empty dir, nothing to lose
            sentinel = os.path.join(SYNCED_D, _slug(d))
            try:
                pulled = os.path.getmtime(sentinel)
            except OSError:
                bad.append(d); continue
            # A sentinel older than the newest file means frames landed after the last pull.
            if pulled < newest - 5 or (now - pulled) > max_age_min * 60:
                bad.append(d)
    return bad


def outputs_synced(max_age_min=15.0, roots=()):
    """True only if nothing is known to be unsynced.

    With --outputs-root given this is a real check per directory. Without it we fall back
    to the global sentinel, which is WEAK — it proves some loop ran, not that this pod's
    work is safe — so the caller logs that it is relying on the weak form.
    """
    if roots:
        return not unsynced_dirs(roots, max_age_min)
    try:
        return (time.time() - os.path.getmtime(SYNCED)) < max_age_min * 60
    except OSError:
        return False


def retire_pod(pod_id, key, dry, why, roots=()):
    """Stop if the pod can actually be restarted; otherwise terminate rather than strand.

    Never leaves a pod billing: the one case we refuse to act on is 'cannot pause safely
    AND outputs are not confirmed on the laptop', which is the only situation where both
    alternatives destroy something. That case logs loudly every poll instead of going quiet.
    """
    stock = gpu_stock(pod_id, key)
    unsynced = unsynced_dirs(roots) if roots else None
    synced = outputs_synced(roots=roots)
    log("%s | gpu stock=%s | outputs synced=%s%s" % (
        why, stock, synced,
        (" (unsynced: %s)" % unsynced) if unsynced else
        ("" if roots else " [WEAK: no --outputs-root, global sentinel only]")))
    if stock == "High":
        log("stock is High - a stop should be resumable; stopping")
        return stop_pod(pod_id, key, dry)
    if synced:
        log("stock=%s: a stop would likely STRAND this pod. Outputs are synced, so "
            "terminating instead - re-provisioning is cheaper than an unreachable volume."
            % stock)
        return terminate_pod(pod_id, key, dry)
    log("WILL NOT RETIRE: stock=%s so a stop risks stranding, and outputs are NOT "
        "confirmed local (%s) so a terminate risks losing work. Run sync-outputs.sh."
        % (stock, unsynced if unsynced else SYNCED))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pod-id", required=True)
    ap.add_argument("--idle-min", type=float, default=15.0)
    ap.add_argument("--comfy", default="http://127.0.0.1:8188")
    ap.add_argument("--poll-sec", type=float, default=30.0)
    ap.add_argument("--max-hours", type=float, default=12.0,
                    help="hard ceiling: stop regardless of activity (runaway-cost backstop)")
    ap.add_argument("--outputs-root", action="append", default=[],
                    help="dir whose SUBDIRS are render outputs; each must have a fresh "
                         "per-directory sentinel before a terminate is considered safe. "
                         "Repeatable. Without it the global sentinel is used, which only "
                         "proves SOME sync loop ran - not that this pod's work is safe")
    ap.add_argument("--lock-ttl-min", type=float, default=20.0,
                    help="/workspace/.busy is a HEARTBEAT: ignored once this stale. "
                         "Long jobs must re-touch it (hold-busy.sh)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    key = (os.environ.get("RUNPOD_API_KEY") or "").strip()
    SECRETS.append(key)
    if not key and not a.dry_run:
        sys.exit("RUNPOD_API_KEY not in env - refusing to start (could never stop the pod)")

    start = time.time(); last_busy = time.time(); idle_s = a.idle_min * 60
    log("watchdog up: pod=%s idle-limit=%.0fmin poll=%.0fs max=%.1fh lock-ttl=%.0fmin" %
        (a.pod_id, a.idle_min, a.poll_sec, a.max_hours, a.lock_ttl_min))
    while True:
        time.sleep(a.poll_sec)
        if time.time() - start > a.max_hours * 3600:
            if retire_pod(a.pod_id, key, a.dry_run, "MAX-HOURS ceiling hit", a.outputs_root):
                return
            log("retire FAILED or refused - pod still billing; retrying next poll")
            continue
        held, age = lock_held(a.lock_ttl_min)
        if held:
            last_busy = time.time()
            log("lock fresh (%s, %.0fs old) - holding" % (LOCK, age))
            continue
        if age is not None:
            log("lock STALE (%.1f min > %.1f min ttl) - ignoring it; the job that took it "
                "did not release or refresh it" % (age / 60.0, a.lock_ttl_min))
        busy = comfy_busy(a.comfy)
        if busy is None:
            last_busy = time.time()          # unreachable != idle (may be booting)
            log("comfy unreachable - holding")
            continue
        if busy:
            last_busy = time.time()
            continue
        idle_for = time.time() - last_busy
        if idle_for >= idle_s:
            if retire_pod(a.pod_id, key, a.dry_run,
                          "idle %.1fmin >= %.1fmin" % (idle_for / 60, a.idle_min),
                          a.outputs_root):
                return
            # NEVER exit while the pod may still bill: retry every poll until it is gone.
            log("retire FAILED or refused - pod still billing; retrying next poll")
            continue
        log("idle %.1fmin (limit %.1f)" % (idle_for / 60, a.idle_min))


if __name__ == "__main__":
    sys.exit(main())
