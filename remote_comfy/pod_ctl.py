#!/usr/bin/env python3
"""RunPod control via the REST v1 API — list / status / stop / start / terminate /
create pods without the dashboard. (The GraphQL API is Cloudflare-blocked → 403
1010; REST v1 works. 2026-07-19.) Key resolves:
  env RUNPOD_API_KEY  ->  OS keyring (optional `pip install keyring`; service and user
  from REMOTE_COMFY_KEYRING_SERVICE / REMOTE_COMFY_KEYRING_USER, default remote-comfy / runpod).

  python pod_ctl.py list
  python pod_ctl.py status <podId>
  python pod_ctl.py stop   <podId>        # keeps the volume; metering stops
  python pod_ctl.py start  <podId>        # resume a stopped pod
  python pod_ctl.py terminate <podId>     # DESTROYS pod-local disk — confirms first
  python pod_ctl.py create --name i2v --gpu "NVIDIA A40" --volume-gb 120 \
       --network-volume <id> --ports "8188/http,22/tcp"
"""
import argparse, json, os, sys, urllib.request, urllib.error

BASE = "https://rest.runpod.io/v1"


def key():
    k = os.environ.get("RUNPOD_API_KEY")
    if k:
        return k
    try:
        import keyring
        k = keyring.get_password(os.environ.get("REMOTE_COMFY_KEYRING_SERVICE", "remote-comfy"),
                                 os.environ.get("REMOTE_COMFY_KEYRING_USER", "runpod"))
        if k:
            return k
    except Exception:
        pass
    sys.exit("no RUNPOD_API_KEY — export it, or store it with "
             "`python -m keyring set remote-comfy runpod`")


BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"


def req(method, path, body=None):
    # Since ~Oct 2026 Cloudflare 1010s urllib's default UA on REST too, not just GraphQL.
    r = urllib.request.Request(BASE + path, method=method,
                               data=(json.dumps(body).encode() if body is not None else None),
                               headers={"Authorization": "Bearer " + key(),
                                        "Content-Type": "application/json",
                                        "User-Agent": BROWSER_UA})
    try:
        raw = urllib.request.urlopen(r, timeout=45).read()
        return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        sys.exit("API %s %s: %s" % (method, path, e.read().decode()[:400]))


def _fmt(p):
    line = "%s  %-20s  %-9s  $%s/hr" % (p.get("id"), (p.get("name") or "")[:20],
                                        p.get("desiredStatus"), p.get("costPerHr"))
    ports = p.get("portMappings") or {}
    pubip = p.get("publicIp") or "?"
    extra = "  ip=%s ports=%s" % (pubip, ports) if ports else ""
    return line + extra


def cmd_list(_a):
    d = req("GET", "/pods")
    pods = d if isinstance(d, list) else d.get("pods", [])
    if not pods:
        print("(no pods)"); return
    for p in pods:
        print(_fmt(p))


def cmd_status(a):
    print(json.dumps(req("GET", "/pods/" + a.podId), indent=1))


def cmd_conn(a):
    """Current SSH connection string. ALWAYS resolve this after a stop/start —
    RunPod REMAPS the SSH port on resume (ip may stay, port changes). Hardcoding a
    port from before a pause is a guaranteed 'Connection refused' rabbit-hole."""
    d = req("GET", "/pods/" + a.podId)
    ip = d.get("publicIp") or ""
    port = (d.get("portMappings") or {}).get("22") or ""
    print("status: %s" % d.get("desiredStatus"))
    if ip and port:
        print("ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p %s root@%s" % (port, ip))
        print("SSH_HOST=%s" % ip)
        print("SSH_PORT=%s" % port)
    else:
        print("(not ready: ip=%r port=%r)" % (ip, port))


def cmd_stop(a):
    req("POST", "/pods/%s/stop" % a.podId)
    print("stopped", a.podId, "(volume kept; metering stopped)")


def cmd_start(a):
    req("POST", "/pods/%s/start" % a.podId)
    print("started", a.podId)


def cmd_terminate(a):
    if input("Terminate %s? pod-local disk DESTROYED. type 'yes': " % a.podId).strip() != "yes":
        print("aborted"); return
    req("DELETE", "/pods/" + a.podId)
    print("terminated", a.podId)


def _gql(query):
    # REST has no availability endpoint; GraphQL has it but Cloudflare-blocks plain
    # urllib (403 1010) — a browser User-Agent bypasses it. Learned 2026-07-19.
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"
    r = urllib.request.Request("https://api.runpod.io/graphql", data=json.dumps({"query": query}).encode(),
                               headers={"Content-Type": "application/json", "Authorization": "Bearer " + key(), "User-Agent": ua})
    return json.loads(urllib.request.urlopen(r, timeout=30).read())["data"]


def cmd_balance(a):
    """Account balance + the burn rate of every RUNNING pod, and hours left at that rate.

    WHY: for a whole session I projected budgets from guesses ("that leaves ~$1 of
    margin") while the real number was one API call away, and was wrong — the account
    actually had $50. A rented-GPU decision is a budget decision; read the
    budget. GraphQL only (REST v1 exposes no billing), so it needs the browser UA.
    """
    d = _gql("query { myself { clientBalance currentSpendPerHr } }")["myself"]
    bal, rate = d.get("clientBalance") or 0.0, d.get("currentSpendPerHr") or 0.0
    print("balance        $%.2f" % bal)
    print("spend rate     $%.2f/hr" % rate)
    if rate > 0:
        print("runway         %.1f h at the current rate" % (bal / rate))
    else:
        print("runway         no pods billing right now")
    return bal, rate


def cmd_availability(a):
    """Which GPUs (>= --min-vram) are in-stock in NETWORK-VOLUME datacenters.
    A GPU's global 'High' stock is often all in community DCs with no volume support,
    so always filter to storage DCs before making a volume there. Match GPU arch to
    your image: Ada/Ampere (RTX 6000 Ada, 4090, A40, A6000) for cuda12.4; Blackwell
    (RTX PRO 4500/5090, B200) needs cuda12.8+/torch2.7+."""
    dcs = [d["id"] for d in _gql("query{dataCenters{id storageSupport}}")["dataCenters"] if d.get("storageSupport")]
    ok = {"High", "Medium", "Low"}
    print("GPUs >= %dGB in-stock in network-volume DCs:" % a.min_vram)
    for dc in dcs:
        q = 'query{gpuTypes{displayName memoryInGb securePrice lowestPrice(input:{gpuCount:1,dataCenterId:"%s"}){stockStatus}}}' % dc
        try:
            gt = _gql(q)["gpuTypes"]
        except Exception:
            continue
        av = [(g["displayName"], g["memoryInGb"], g["lowestPrice"]["stockStatus"], g.get("securePrice"))
              for g in gt if g.get("memoryInGb", 0) >= a.min_vram and g["lowestPrice"]["stockStatus"] in ok]
        if av:
            print("  %-10s" % dc, ", ".join("%s(%sGB,%s,$%s)" % x for x in sorted(av, key=lambda z: z[3] or 99)[:6]))


def cmd_create(a):
    body = {"name": a.name, "imageName": a.image, "gpuTypeIds": [a.gpu], "gpuCount": a.gpu_count,
            "containerDiskInGb": a.container_gb, "volumeMountPath": "/workspace",
            "ports": [p.strip() for p in a.ports.split(",")], "cloudType": "SECURE"}
    if a.network_volume:
        body["networkVolumeId"] = a.network_volume
    else:
        body["volumeInGb"] = a.volume_gb
    d = req("POST", "/pods", body)
    print("created:", json.dumps(d, indent=1)[:600])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(f=cmd_list)
    sub.add_parser("balance").set_defaults(f=cmd_balance)
    cn = sub.add_parser("conn"); cn.add_argument("podId"); cn.set_defaults(f=cmd_conn)
    av = sub.add_parser("availability"); av.add_argument("--min-vram", type=int, default=32); av.set_defaults(f=cmd_availability)
    for name in ("status", "stop", "start", "terminate"):
        sp = sub.add_parser(name); sp.add_argument("podId"); sp.set_defaults(f=globals()["cmd_" + name])
    sc = sub.add_parser("create")
    sc.add_argument("--name", default="comfy")
    sc.add_argument("--gpu", default="NVIDIA A40")
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
