#!/usr/bin/env python3
"""RunPod control via REST v2: list / status / stop / start / terminate / create pods,
plus balance and GPU availability, without the dashboard.

REST v1 (rest.runpod.io) was retired on 2026-11-15 and GraphQL is deprecated (retires
early 2027), so everything here uses https://api.runpod.io/v2. Key resolves:
  env RUNPOD_API_KEY  ->  OS keyring (optional `pip install keyring`; service and user
  from REMOTE_COMFY_KEYRING_SERVICE / REMOTE_COMFY_KEYRING_USER, default remote-comfy / runpod).

  python pod_ctl.py list
  python pod_ctl.py status <podId>
  python pod_ctl.py conn   <podId>        # current SSH address (it changes on every restart)
  python pod_ctl.py stop   <podId>        # keeps the volume; GPU metering stops
  python pod_ctl.py start  <podId>        # resume a stopped pod
  python pod_ctl.py terminate <podId>     # DESTROYS pod-local disk; confirms first
  python pod_ctl.py balance
  python pod_ctl.py availability --min-vram 48
  python pod_ctl.py create --name i2v --gpu "NVIDIA L40S,NVIDIA A40" --gpu-count 2 \
       --volume-gb 200 --ports "8188/http,22/tcp"
"""
import argparse, calendar, json, os, sys, time, urllib.error, urllib.parse, urllib.request

BASE = "https://api.runpod.io/v2"


def key():
    k = (os.environ.get("RUNPOD_API_KEY") or "").strip()   # a pasted or piped key carries \r
    if k:
        return k
    try:
        import keyring
        k = keyring.get_password(os.environ.get("REMOTE_COMFY_KEYRING_SERVICE", "remote-comfy"),
                                 os.environ.get("REMOTE_COMFY_KEYRING_USER", "runpod"))
        if k:
            return k.strip()
    except Exception:
        pass
    sys.exit("no RUNPOD_API_KEY - export it, or store it with "
             "`python -m keyring set remote-comfy runpod`")


BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"


class ApiError(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, "HTTP %s: %s" % (code, detail))
        self.code, self.detail = code, detail


def req(method, path, body=None, fatal=True):
    # Cloudflare 1010'd urllib's default UA on the old APIs; every request sends a browser UA.
    r = urllib.request.Request(BASE + path, method=method,
                               data=(json.dumps(body).encode() if body is not None else None),
                               headers={"Authorization": "Bearer " + key(),
                                        "Content-Type": "application/json",
                                        "User-Agent": BROWSER_UA})
    try:
        raw = urllib.request.urlopen(r, timeout=45).read()
        return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            detail = json.loads(text).get("detail") or text
        except ValueError:
            detail = text
        if fatal:
            sys.exit("API %s %s: HTTP %s %s" % (method, path, e.code, str(detail)[:400]))
        raise ApiError(e.code, str(detail)[:400])


def _cost(p):
    c = p.get("cost")
    if isinstance(c, dict):
        c = c.get("perHour") or c.get("hourly") or c.get("total")
    return c


def _fmt(p):
    gpu = p.get("gpu") or {}
    return "%s  %-20s  %-12s  %sx %-24s  $%s/hr  %s" % (
        p.get("id"), (p.get("name") or "")[:20], p.get("status"), gpu.get("count"),
        gpu.get("id"), _cost(p), p.get("dataCenterId") or "")


def _pods():
    pods, cursor = [], None
    while True:
        d = req("GET", "/pods" + ("?" + urllib.parse.urlencode({"cursor": cursor}) if cursor else ""))
        pods += d.get("pods") or []
        page = d.get("pagination") or {}
        if not page.get("hasNextPage"):
            return pods
        cursor = page.get("nextCursor")


def cmd_list(_a):
    pods = _pods()
    if not pods:
        print("(no pods)"); return
    for p in pods:
        print(_fmt(p))


def cmd_status(a):
    print(json.dumps(req("GET", "/pods/" + a.podId), indent=1))


def _fresh_ssh(d, now=None, slack=30):
    """(host, port) of THIS run's SSH mapping, or ("", "") while the record is stale."""
    if d.get("status") != "RUNNING":
        return "", ""
    rt = d.get("runtime") or {}
    try:
        started = calendar.timegm(time.strptime((d.get("startedAt") or "")[:19], "%Y-%m-%dT%H:%M:%S"))
        uptime = float(rt.get("uptime"))
    except (TypeError, ValueError):
        return "", ""
    if uptime > (now if now is not None else time.time()) - started + slack:
        return "", ""                       # the uptime of a run that began before this start
    for m in rt.get("ports") or []:
        if m.get("private") == 22 and m.get("type") == "tcp" and m.get("ip") and m.get("public"):
            return m["ip"], m["public"]
    return "", ""


def cmd_conn(a):
    """Current SSH connection string. ALWAYS resolve this after a stop/start -
    RunPod REMAPS the SSH port on resume (ip may stay, port changes). Hardcoding a
    port from before a pause is a guaranteed 'Connection refused' rabbit-hole.
    v2 serves the PREVIOUS run's address for a few seconds after a start: on 2026-11-20
    status was RUNNING, ssh.direct and runtime.ports both showed the pre-stop port, and
    runtime.uptime was 582 s although startedAt was 11 s old. So the address counts only
    when status is RUNNING and the uptime fits inside the time since startedAt. Both fields
    also blink out for a poll now and then. Not ready = poll again.
    ssh.proxy is PTY-only (no scp, no -L)."""
    d = req("GET", "/pods/" + a.podId)
    host, port = _fresh_ssh(d)
    print("status: %s" % d.get("status"))
    if host and port:
        print("ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p %s root@%s" % (port, host))
        print("SSH_HOST=%s" % host)
        print("SSH_PORT=%s" % port)
    else:
        print("(not ready: host=%r port=%r)" % (host, port))


def _action(pod_id, action):
    return req("POST", "/pods/%s/action" % pod_id, {"action": action})


def cmd_stop(a):
    _action(a.podId, "stop")
    print("stopped", a.podId, "(volume kept; GPU metering stopped)")


def cmd_start(a):
    _action(a.podId, "start")
    print("started", a.podId, "- run `conn` again: the SSH port can change on every start")


def cmd_terminate(a):
    if input("Terminate %s? pod-local disk DESTROYED. type 'yes': " % a.podId).strip() != "yes":
        print("aborted"); return
    req("DELETE", "/pods/" + a.podId)
    print("terminated", a.podId)


def cmd_balance(a):
    """Account balance + the burn rate of every RUNNING pod, and hours left at that rate.

    WHY: for a whole session I projected budgets from guesses ("that leaves ~$1 of
    margin") while the real number was one API call away, and was wrong - the account
    actually had $50. A rented-GPU decision is a budget decision; read the budget.
    """
    d = req("GET", "/billing/balance")
    bal = float(d.get("balanceAmount") or 0.0)
    rate = 0.0
    for p in _pods():
        c = _cost(p)
        if p.get("status") == "RUNNING" and isinstance(c, (int, float)):
            rate += c
    print("balance        $%.2f  (%s)" % (bal, d.get("billingMode") or "?"))
    print("spend rate     $%.2f/hr" % rate)
    if rate > 0:
        print("runway         %.1f h at the current rate" % (bal / rate))
    else:
        print("runway         no pods billing right now")
    return bal, rate


def cmd_availability(a):
    """GPUs with >= --min-vram GB that RunPod reports in stock for pods, cheapest first, with
    the data centres that have them. Match GPU arch to the image: Ada/Ampere/Hopper (L40S,
    RTX 6000 Ada, 4090, A40, H100) for CUDA 12.x images; Blackwell (RTX PRO 6000, 5090, B200)
    needs CUDA 12.8+ and torch 2.7+, which provision-comfyui.sh does not install."""
    q = urllib.parse.urlencode({"include": "AVAILABILITY", "product": "POD",
                                "count": a.gpu_count, "cloud": "SECURE"})
    gpus = req("GET", "/catalog/gpus?" + q).get("gpus") or []
    rows = []
    for g in gpus:
        if (g.get("memory") or 0) < a.min_vram or g.get("availability") in (None, "NONE"):
            continue
        price = (g.get("price") or {}).get("secure")
        dcs = [d["id"] for d in (g.get("dataCenters") or []) if d.get("availability") not in (None, "NONE")]
        rows.append((price if price is not None else 99, g.get("id"), g.get("memory"), g.get("availability"), dcs))
    print("GPUs >= %dGB in stock for %d-GPU pods (secure cloud, $ per GPU-hour):" % (a.min_vram, a.gpu_count))
    for price, gid, mem, av, dcs in sorted(rows):
        print("  %-34s %4sGB  %-6s $%-5s %s" % (gid, mem, av, price, " ".join(dcs[:6])))
    if not rows:
        print("  (none)")


def cmd_create(a):
    """One GPU type per pod in v2. --gpu takes a comma list, tried in order: a 400 is how
    v2 reports no capacity (only a human-readable detail), so the next type is tried; any
    other error stops. Pod-local /workspace by default; a network volume DC-locks you."""
    body = {"name": a.name, "image": a.image, "gpu": {"id": None, "count": a.gpu_count},
            "disk": a.container_gb, "ports": [p.strip() for p in a.ports.split(",")],
            "cloud": "SECURE", "startSsh": True}
    if a.network_volume:
        body["mounts"] = {"network": [{"volumeId": a.network_volume, "path": "/workspace"}]}
    else:
        body["mounts"] = {"persistent": {"size": a.volume_gb, "path": "/workspace"}}
    for gpu in [g.strip() for g in a.gpu.split(",") if g.strip()]:
        body["gpu"]["id"] = gpu
        try:
            d = req("POST", "/pods", body, fatal=False)
        except ApiError as e:
            if e.code == 400:
                print("no capacity for %s (%s); trying the next type" % (gpu, e.detail[:120]))
                continue
            sys.exit("create failed for %s: %s" % (gpu, e))
        print("created:", json.dumps(d, indent=1)[:600])
        return d
    sys.exit("no capacity for any of: %s" % a.gpu)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(f=cmd_list)
    sub.add_parser("balance").set_defaults(f=cmd_balance)
    cn = sub.add_parser("conn"); cn.add_argument("podId"); cn.set_defaults(f=cmd_conn)
    av = sub.add_parser("availability"); av.add_argument("--min-vram", type=int, default=32)
    av.add_argument("--gpu-count", type=int, default=1); av.set_defaults(f=cmd_availability)
    for name in ("status", "stop", "start", "terminate"):
        sp = sub.add_parser(name); sp.add_argument("podId"); sp.set_defaults(f=globals()["cmd_" + name])
    sc = sub.add_parser("create")
    sc.add_argument("--name", default="comfy")
    sc.add_argument("--gpu", default="NVIDIA A40", help="GPU type id, or a comma list tried in order")
    sc.add_argument("--gpu-count", type=int, default=1)
    sc.add_argument("--image", default="runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04")
    sc.add_argument("--container-gb", type=int, default=30)
    sc.add_argument("--volume-gb", type=int, default=120)
    sc.add_argument("--network-volume", default=None)
    sc.add_argument("--ports", default="8188/http,22/tcp")
    sc.set_defaults(f=cmd_create)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
