#!/usr/bin/env python3
"""Executable tripwires for the RunPod/ComfyUI operating lessons (2026-07-25).

Repo rule: test > hook > lint > sidecar > comment. Each assertion below is a lesson
that cost real time or real money; if someone regresses it, this fails instead of
the lesson quietly rotting in a README.

  python tests/test_runpod_ops.py        # no network, no GPU, no API key needed

When you learn a new lesson, add its assertion HERE first, then the prose in docs/.
"""
import argparse, calendar, importlib.util, io, os, sys, tempfile, threading, time, json
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAIL = []

# Where each tool lives in the repo. Tests reference tools by name only.
PATHS = {
    "autostop.py": "remote_comfy/autostop.py",
    "pod_ctl.py": "remote_comfy/pod_ctl.py",
    "comfy_client.py": "remote_comfy/comfy_client.py",
    "check_latest_models.py": "remote_comfy/check_latest_models.py",
    "provision-comfyui.sh": "pod/provision-comfyui.sh",
    "launch-sharded.sh": "pod/launch-sharded.sh",
    "hold-busy.sh": "pod/hold-busy.sh",
    "check-gpu-load.sh": "pod/check-gpu-load.sh",
    "sync-outputs.sh": "local/sync-outputs.sh",
}
# The prose an agent reads. Doc assertions search all of it, so a trap may live in
# whichever file fits, but must not vanish from all of them.
DOCS = ["AGENTS.md", "skills/remote-comfy/SKILL.md", "docs/playbook.md",
        "docs/traps.md", "docs/gpu-choice.md", "docs/open-questions.md"]


def P(name):
    return os.path.join(ROOT, *PATHS[name].split("/"))


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


def load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


class _Q(BaseHTTPRequestHandler):
    payload = {"queue_running": [], "queue_pending": []}

    def do_GET(self):
        body = json.dumps(self.payload).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    au = load("autostop", P("autostop.py"))
    pod_ctl_src = io.open(P("pod_ctl.py"), encoding="utf-8").read()
    readme = "\n".join(io.open(os.path.join(ROOT, *d.split("/")), encoding="utf-8").read()
                        for d in DOCS)

    # --- LESSON: SSH port REMAPS on stop/start. Tooling must resolve it, never hardcode.
    check("def cmd_conn" in pod_ctl_src and '"conn"' in pod_ctl_src,
          "pod_ctl exposes `conn` to resolve the CURRENT ssh port (port remaps on resume)")
    check("REMAP" in pod_ctl_src.upper() or "remaps" in pod_ctl_src,
          "pod_ctl documents the port-remap trap at the point of use")

    # --- LESSON (2026-11-15): RunPod retired REST v1; rest.runpod.io no longer resolves, so
    # every pod call (list, create, conn, stop, terminate) and the watchdog's stop/terminate
    # failed with getaddrinfo. GraphQL is deprecated too (retires early 2027). Both tools use
    # REST v2 only.
    au_src0 = io.open(P("autostop.py"), encoding="utf-8").read()
    for name, src in (("pod_ctl.py", pod_ctl_src), ("autostop.py", au_src0)):
        check("https://rest.runpod.io" not in src and "/graphql" not in src.lower(),
              "%s calls neither the retired REST v1 nor the deprecated GraphQL API" % name)
        check("https://api.runpod.io/v2" in src, "%s uses RunPod REST v2" % name)
    check("2026-11-15" in readme and "retired" in readme and "api.runpod.io/v2" in readme,
          "docs record that REST v1 was retired on 2026-11-15 and the tools use v2")

    # --- LESSON: network volumes DC-lock you; default must be pod-local disk.
    check('"persistent"' in pod_ctl_src and '"network"' in pod_ctl_src,
          "pod_ctl supports pod-local volume (no network volume) to avoid DC-locking")
    check("--network-volume" in pod_ctl_src and 'default=None' in pod_ctl_src,
          "network volume is OPT-IN (default None), not the default")

    # --- LESSON: multi-GPU is same total cost, just faster -> must be reachable.
    check("--gpu-count" in pod_ctl_src and "a.gpu_count" in pod_ctl_src,
          "pod_ctl can create multi-GPU pods (gpuCount wired through)")

    # --- LESSON: a watchdog that cannot authenticate can never stop the pod.
    argv, env = sys.argv[:], os.environ.pop("RUNPOD_API_KEY", None)
    sys.argv = ["autostop.py", "--pod-id", "x"]
    try:
        au.main(); refused = False
    except SystemExit as e:
        refused = "RUNPOD_API_KEY" in str(e)
    except Exception:
        refused = False
    finally:
        sys.argv = argv
        if env:
            os.environ["RUNPOD_API_KEY"] = env
    check(refused, "autostop REFUSES to run without RUNPOD_API_KEY (else it strands a billing pod)")

    # --- LESSON: unreachable ComfyUI is NOT idle (it may be booting) -> must not stop.
    check(au.comfy_busy("http://127.0.0.1:9", timeout=2) is None,
          "unreachable ComfyUI returns None (not False) so a booting pod is never killed")

    # --- live idle/busy detection against a real HTTP server
    srv = HTTPServer(("127.0.0.1", 0), _Q)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d" % srv.server_address[1]
    _Q.payload = {"queue_running": [], "queue_pending": []}
    check(au.comfy_busy(url) is False, "empty queue detected as IDLE")
    _Q.payload = {"queue_running": [["job"]], "queue_pending": []}
    check(au.comfy_busy(url) is True, "running job detected as BUSY")
    _Q.payload = {"queue_running": [], "queue_pending": [["job"]]}
    check(au.comfy_busy(url) is True, "PENDING job detected as BUSY (not just running)")
    srv.shutdown()

    # --- LESSON: long non-ComfyUI work (24GB download) must be able to block the stop.
    check(au.LOCK == "/workspace/.busy",
          "lockfile path is the documented /workspace/.busy")
    src = io.open(P("autostop.py"), encoding="utf-8").read()
    # The lock must still be honoured — but via freshness, not bare existence. This check
    # originally asserted `os.path.exists(LOCK)`; that is now the BUG, so it asserts the
    # replacement instead of being deleted, keeping the original guarantee intact.
    check("lock_held(" in src and "last_busy = time.time()" in src,
          "watchdog honours a FRESH lockfile before stopping")
    check("--max-hours" in src, "watchdog has a hard max-hours runaway-cost ceiling")

    # --- LESSON (2026-07-27): THE LOCK IS A HEARTBEAT, NOT A FLAG. A sweep script touched
    # .busy and exited without removing it; the watchdog "held" a fully idle pod for 3
    # hours (~$9). A lock that outlives its job looks exactly like one nobody cleaned up,
    # so it must EXPIRE rather than be trusted for existing.
    check(hasattr(au, "lock_held"), "watchdog checks lock FRESHNESS, not mere existence")
    au_src0 = io.open(P("autostop.py"), encoding="utf-8").read()
    check("os.path.exists(LOCK)" not in au_src0,
          "no path treats a bare existing lockfile as authoritative")
    check("--lock-ttl-min" in au_src0, "lock TTL is configurable")
    if hasattr(au, "lock_held"):
        tmpd = tempfile.mkdtemp(); lk = os.path.join(tmpd, ".busy")
        real_lock = au.LOCK
        try:
            au.LOCK = lk
            held, age = au.lock_held(20.0)
            check(held is False and age is None, "absent lock -> not held")
            open(lk, "w").close()
            held, age = au.lock_held(20.0)
            check(held is True, "freshly touched lock -> held")
            os.utime(lk, (time.time() - 3600, time.time() - 3600))   # 60 min old
            held, age = au.lock_held(20.0)
            check(held is False and age > 3000,
                  "STALE lock (60min > 20min ttl) -> ignored, so a forgotten lock cannot "
                  "hold a pod forever")
        finally:
            au.LOCK = real_lock
    hb = P("hold-busy.sh")
    check(os.path.exists(hb), "hold-busy.sh exists (refreshes the lock while a job runs)")
    if os.path.exists(hb):
        hbs = io.open(hb, encoding="utf-8").read()
        check("trap release EXIT INT TERM" in hbs,
              "hold-busy releases the lock on exit, interrupt AND terminate")

    # --- LESSON (2026-07-27): a STOP is only a pause when the GPU is easy to get back.
    # Stopping an L40S pod while L40S stock was Low stranded it permanently: the host
    # refilled, `start` returned "not enough free GPUs on the host machine", and 50GB of
    # weights on its pod-local volume became unreachable while still billing storage.
    # The watchdog must check stock, and must have a safe alternative to stranding.
    check(hasattr(au, "gpu_stock"), "watchdog can query GPU stock before retiring a pod")
    check(hasattr(au, "terminate_pod"), "watchdog can terminate, not only stop")
    check(hasattr(au, "outputs_synced"), "watchdog knows whether outputs reached the laptop")
    au_src = io.open(P("autostop.py"), encoding="utf-8").read()
    check("stop_pod(a.pod_id" not in au_src,
          "no direct stop path bypasses the strand check (all retirement goes via retire_pod)")

    # Behavioural: prove each branch, with a fake stock/sync so no API is touched.
    calls = []
    real = (au.gpu_stock, au.outputs_synced, au.stop_pod, au.terminate_pod)
    au.stop_pod = lambda *a, **k: calls.append("stop")
    au.terminate_pod = lambda *a, **k: calls.append("terminate")
    try:
        au.gpu_stock = lambda *a, **k: "High"; au.outputs_synced = lambda *a, **k: False
        calls[:] = []; au.retire_pod("p", "k", True, "t")
        check(calls == ["stop"], "High stock -> STOP (restartable, keeps the weights)")

        au.gpu_stock = lambda *a, **k: "Low"; au.outputs_synced = lambda *a, **k: True
        calls[:] = []; au.retire_pod("p", "k", True, "t")
        check(calls == ["terminate"],
              "Low stock + outputs synced -> TERMINATE (never strand, never keep billing)")

        au.gpu_stock = lambda *a, **k: "Low"; au.outputs_synced = lambda *a, **k: False
        calls[:] = []; ret = au.retire_pod("p", "k", True, "t")
        check(calls == [] and ret is False,
              "Low stock + outputs NOT synced -> refuse both (would strand or lose work)")
    finally:
        au.gpu_stock, au.outputs_synced, au.stop_pod, au.terminate_pod = real

    # --- LESSONS (2026-10-23, live 2xA40 smoke test): the watchdog decided correctly and
    # then could not act. Its REST calls lacked a browser UA (Cloudflare 403), the failed
    # terminate was swallowed, and main() EXITED, leaving the pod billing unguarded.
    seen = []

    # REST v2 shapes (docs.runpod.io/api-reference-v2, read 2026-11-19): a pod has gpu.id,
    # gpu.count, cloud and dataCenterId; the catalogue answers availability NONE/LOW/MEDIUM/
    # HIGH per GPU and per data centre. This fake answers by URL, like the real API.
    class _Resp:
        def __init__(self, body):
            self.body = body

        def read(self):
            return json.dumps(self.body).encode() if self.body is not None else b""

    def _fake_v2(r, timeout=None):
        seen.append(r)
        u = r.full_url
        if "/catalog/gpus" in u:
            return _Resp({"gpus": [{"id": "Y", "availability": "HIGH"},
                                   {"id": "X", "availability": "HIGH",
                                    "dataCenters": [{"id": "EU-NL-1", "availability": "LOW"}]}]})
        if r.get_method() == "GET" and u.endswith("/pods/p"):
            return _Resp({"id": "p", "status": "RUNNING", "cloud": "SECURE", "dataCenterId": "EU-NL-1",
                          "gpu": {"id": "X", "count": 2}})
        return _Resp(None)
    real_open, real_sleep = au.urllib.request.urlopen, au.time.sleep
    au.urllib.request.urlopen = _fake_v2
    au.time.sleep = lambda s: None
    try:
        au.stop_pod("p", "k", False); au.terminate_pod("p", "k", False)
        stock = au.gpu_stock("p", "k")
    finally:
        au.urllib.request.urlopen, au.time.sleep = real_open, real_sleep
    rp = [r for r in seen if "runpod.io" in r.full_url]
    check(len(rp) >= 4 and all("Mozilla" in (r.get_header("User-agent") or "") for r in rp),
          "EVERY RunPod call from the watchdog (stop, terminate, pod read, catalogue) sends a browser UA")
    stops = [r for r in rp if r.full_url.endswith("/v2/pods/p/action")]
    check(len(stops) == 1 and stops[0].get_method() == "POST"
          and json.loads(stops[0].data) == {"action": "stop"},
          "watchdog stops a pod with v2 POST /pods/{id}/action {\"action\": \"stop\"}")
    check(any(r.get_method() == "DELETE" and r.full_url.endswith("/v2/pods/p") for r in rp),
          "watchdog terminates a pod with v2 DELETE /pods/{id}")
    cat = [r for r in rp if "/catalog/gpus" in r.full_url]
    check(cat and "include=AVAILABILITY" in cat[0].full_url and "product=POD" in cat[0].full_url
          and "count=2" in cat[0].full_url,
          "the stock check asks the v2 catalogue for POD availability at this pod's GPU count")
    check(stock == "Low",
          "gpu_stock reads THIS pod's GPU type and its data centre's stock (LOW there, HIGH globally)")

    # pod_ctl on v2: create body, GPU fall-through on a 400 (no capacity), conn from ssh.direct.
    pc = load("pod_ctl", P("pod_ctl.py"))
    sent = []

    def _fake_ctl(r, timeout=None):
        sent.append(r)
        u, m = r.full_url, r.get_method()
        if m == "POST" and u.endswith("/v2/pods"):
            body = json.loads(r.data)
            if body["gpu"]["id"] == "NVIDIA L40S":
                raise pc.urllib.error.HTTPError(u, 400, "Bad Request", {}, io.BytesIO(
                    b'{"title":"Bad Request","status":400,"detail":"no instances available"}'))
            return _Resp({"id": "newpod", "status": "PROVISIONING"})
        if m == "GET" and u.endswith("/v2/pods/newpod"):
            # Shape recorded live 2026-11-20. ssh.direct holds a different (stale) port on
            # purpose: conn must read the runtime mapping, not ssh.direct.
            return _Resp({"id": "newpod", "status": "RUNNING",
                          "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S.5Z", time.gmtime(time.time() - 20)),
                          "runtime": {"uptime": 9, "ports": [
                              {"ip": "100.65.16.9", "private": 8188, "public": 60570, "type": "http"},
                              {"ip": "1.2.3.4", "private": 22, "public": 40022, "type": "tcp"}]},
                          "ssh": {"direct": {"host": "1.2.3.4", "port": 19618}}})
        return _Resp({})
    real_ctl_open, real_key = pc.urllib.request.urlopen, os.environ.get("RUNPOD_API_KEY")
    pc.urllib.request.urlopen = _fake_ctl
    os.environ["RUNPOD_API_KEY"] = "test-key"
    out = io.StringIO()
    real_stdout, sys.stdout = sys.stdout, out
    try:
        pc.cmd_create(argparse.Namespace(name="n", image="img", gpu="NVIDIA L40S,NVIDIA A40", gpu_count=2,
                                         container_gb=30, volume_gb=120, network_volume=None,
                                         ports="8188/http,22/tcp"))
        pc.cmd_conn(argparse.Namespace(podId="newpod"))
    finally:
        sys.stdout = real_stdout
        pc.urllib.request.urlopen = real_ctl_open
        if real_key is None:
            os.environ.pop("RUNPOD_API_KEY", None)
        else:
            os.environ["RUNPOD_API_KEY"] = real_key
    creates = [json.loads(r.data) for r in sent if r.get_method() == "POST" and r.full_url.endswith("/v2/pods")]
    check([c["gpu"]["id"] for c in creates] == ["NVIDIA L40S", "NVIDIA A40"],
          "create tries the next GPU type when one has no capacity (v2 takes one type per pod)")
    c = creates[-1] if creates else {}
    check(c.get("gpu") == {"id": "NVIDIA A40", "count": 2} and c.get("image") == "img"
          and c.get("disk") == 30 and c.get("ports") == ["8188/http", "22/tcp"]
          and c.get("startSsh") is True and c.get("cloud") == "SECURE"
          and c.get("mounts") == {"persistent": {"size": 120, "path": "/workspace"}},
          "create sends the v2 body: gpu{id,count}, image, disk, ports, startSsh, SECURE, a pod-local /workspace")
    text = out.getvalue()
    check("SSH_HOST=1.2.3.4" in text and "SSH_PORT=40022" in text,
          "conn reads this run's port-22 mapping from runtime.ports, not ssh.direct")

    # LESSON (2026-11-20, live 4090): right after a start v2 served the PREVIOUS run's
    # address (RUNNING, old port in ssh.direct and runtime.ports, uptime 582 s while
    # startedAt was 11 s old); a stopped pod kept its old ssh.direct too.
    t0 = calendar.timegm((2026, 11, 20, 4, 15, 44, 0, 0, 0))
    live = {"status": "RUNNING", "startedAt": "2026-11-20T04:15:44.902Z",
            "runtime": {"uptime": 582, "ports": [{"ip": "203.0.113.7", "private": 22,
                                                  "public": 19618, "type": "tcp"}]},
            "ssh": {"direct": {"host": "203.0.113.7", "port": 19618}}}
    check(pc._fresh_ssh(live, now=t0 + 11) == ("", ""),
          "conn refuses a stale address: runtime.uptime longer than the time since startedAt")
    fresh = json.loads(json.dumps(live)); fresh["runtime"]["uptime"] = 9
    fresh["runtime"]["ports"][0]["public"] = 12358
    check(pc._fresh_ssh(fresh, now=t0 + 18) == ("203.0.113.7", 12358),
          "conn accepts the new mapping once the uptime fits this start")
    stopped = json.loads(json.dumps(fresh)); stopped["status"] = "EXITED"
    check(pc._fresh_ssh(stopped, now=t0 + 18) == ("", ""),
          "conn gives no address for a pod that is not RUNNING, whatever ssh.direct says")
    blink = {"status": "RUNNING", "startedAt": "2026-11-20T04:15:44.902Z", "runtime": None,
             "ssh": {"direct": None}}
    check(pc._fresh_ssh(blink, now=t0 + 40) == ("", ""),
          "conn treats a RUNNING pod with no runtime block (it blinks out) as not ready")

    # LESSON (2026-11-20): a key piped from Windows Python ends in \r. urllib refused the
    # header, so the watchdog could never stop the pod, and its error text quoted the key.
    os.environ["RUNPOD_API_KEY"] = "test-key\r\n"
    try:
        check(pc.key() == "test-key", "pod_ctl strips a trailing CR/LF from the key")
    finally:
        if real_key is None:
            os.environ.pop("RUNPOD_API_KEY", None)
        else:
            os.environ["RUNPOD_API_KEY"] = real_key
    seen[:] = []
    au.urllib.request.urlopen, au.time.sleep = _fake_v2, (lambda s: None)
    try:
        au.stop_pod("p", "k\r", False)
    finally:
        au.urllib.request.urlopen, au.time.sleep = real_open, real_sleep
    check(seen and seen[-1].get_header("Authorization") == "Bearer k",
          "the watchdog strips a CR from the key before it builds the header")
    logged = io.StringIO()
    real_stdout, sys.stdout = sys.stdout, logged
    au.SECRETS.append("rpa_SECRET123")
    try:
        au.log("stock check failed: Invalid header value b'Bearer rpa_SECRET123\\r'")
        au.log("echo rpa_SECRET123")
        au.log("header was Bearer unregistered_TOKEN456")   # a key main() never saw
    finally:
        sys.stdout = real_stdout
        au.SECRETS.remove("rpa_SECRET123")
    check("SECRET123" not in logged.getvalue() and "TOKEN456" not in logged.getvalue()
          and "***" in logged.getvalue(),
          "the watchdog's log scrubs the key and any Bearer header from every line")

    def _fail(*a, **k):
        raise au.urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b"1010"))
    au.urllib.request.urlopen, au.time.sleep = _fail, (lambda s: None)
    try:
        check(au.terminate_pod("p", "k", False) is False,
              "a failed terminate returns False (it used to be swallowed)")
    finally:
        au.urllib.request.urlopen, au.time.sleep = real_open, real_sleep

    tries = []

    def _retire(*a, **k):
        tries.append(1)
        if len(tries) > 6:
            raise RuntimeError("runaway")
        return len(tries) >= 3                       # fail twice, then succeed
    saved = (au.retire_pod, au.comfy_busy, au.lock_held, au.time.sleep, sys.argv[:])
    au.retire_pod, au.comfy_busy = _retire, (lambda *a, **k: False)
    au.lock_held, au.time.sleep = (lambda *a, **k: (False, None)), (lambda s: None)
    os.environ["RUNPOD_API_KEY"] = os.environ.get("RUNPOD_API_KEY") or "test-key"
    sys.argv = ["autostop.py", "--pod-id", "p", "--idle-min", "0", "--poll-sec", "0"]
    try:
        au.main()
    except (RuntimeError, SystemExit):
        pass
    finally:
        au.retire_pod, au.comfy_busy, au.lock_held, au.time.sleep, sys.argv = saved
        if env is None:
            os.environ.pop("RUNPOD_API_KEY", None)
    check(len(tries) == 3, "watchdog RETRIES a failed retire every poll instead of exiting "
          "(it exited after one failure and left the pod billing)")

    # Flat outputs: the harness writes files straight into the root.
    froot = tempfile.mkdtemp(); fsd = os.path.join(froot, "sd"); os.makedirs(fsd)
    fout = os.path.join(froot, "out"); os.makedirs(fout)
    open(os.path.join(fout, "a.png"), "w").close()
    real_sd = au.SYNCED_D
    try:
        au.SYNCED_D = fsd
        check(au.unsynced_dirs([fout]) == [fout],
              "files directly in --outputs-root are checked (a flat dir used to read as synced)")
        open(os.path.join(fsd, au._slug(fout)), "w").close()
        check(au.unsynced_dirs([fout + "/"]) == [], "a fresh sentinel for the flat root clears it")
    finally:
        au.SYNCED_D = real_sd

    # The sync loop and the watchdog must derive the SAME sentinel name: run the script's
    # own lines through bash and compare with _slug().
    sy_lines = [l for l in io.open(P("sync-outputs.sh"), encoding="utf-8").read().splitlines()
                if l.startswith(("REMOTE=\"${REMOTE%/}\"", "SLUG="))]
    try:
        import subprocess
        got = subprocess.run(["bash", "-c", "REMOTE=/workspace/out/\n" + "\n".join(sy_lines)
                              + "\nprintf '%s' \"$SLUG\""], capture_output=True, text=True,
                             timeout=30).stdout
    except Exception as e:
        got = str(e)
    check(len(sy_lines) == 2 and got == au._slug("/workspace/out"),
          "sync-outputs.sh and autostop agree on the sentinel name (%r vs %r)"
          % (got, au._slug("/workspace/out")))

    # --- LESSON (2026-07-27): the sync sentinel was GLOBAL, so
    # any running loop asserted that ALL outputs were safe. The terminate-rather-than-
    # strand branch trusts that signal, so it could have destroyed a pod still holding
    # unsynced frames from a different directory.
    check(hasattr(au, "unsynced_dirs"), "watchdog can name which dirs are unsynced")
    check("--outputs-root" in au_src, "outputs roots are configurable for a real check")
    if hasattr(au, "unsynced_dirs"):
        troot = tempfile.mkdtemp()
        sd = os.path.join(troot, "sent"); os.makedirs(sd)
        real_sd = au.SYNCED_D
        try:
            au.SYNCED_D = sd
            a_dir = os.path.join(troot, "outs", "a"); os.makedirs(a_dir)
            b_dir = os.path.join(troot, "outs", "b"); os.makedirs(b_dir)
            open(os.path.join(a_dir, "f.png"), "w").close()
            open(os.path.join(b_dir, "f.png"), "w").close()
            root = os.path.join(troot, "outs")
            bad = au.unsynced_dirs([root])
            check(sorted(bad) == sorted([a_dir, b_dir]),
                  "dirs with output and NO sentinel are reported unsynced")
            # sentinel for a only -> b must still be flagged. This is the exact bug: a
            # global flag would have declared BOTH safe.
            open(os.path.join(sd, au._slug(a_dir)), "w").close()
            bad = au.unsynced_dirs([root])
            check(bad == [b_dir],
                  "a sentinel for ONE dir does not vouch for another (the global-flag bug)")
            # frames landing after the pull must re-flag the dir
            time.sleep(0.01)
            os.utime(os.path.join(a_dir, "f.png"), (time.time() + 60, time.time() + 60))
            check(a_dir in au.unsynced_dirs([root]),
                  "frames written AFTER the last pull re-flag the dir as unsynced")
        finally:
            au.SYNCED_D = real_sd

    # The sentinel is only meaningful if the sync loop actually writes it.
    sy = io.open(P("sync-outputs.sh"), encoding="utf-8").read()
    check("/workspace/.synced" in sy, "sync loop touches the sentinel the watchdog reads")
    check(au.SYNCED == "/workspace/.synced", "both sides agree on the sentinel path")
    # The watchdog's per-directory check is worthless unless the loop WRITES per-directory.
    # Caught by a negative control: breaking the per-dir write left every test passing.
    check("/workspace/.synced.d/$SLUG" in sy,
          "sync loop writes a PER-DIRECTORY sentinel, not only the global one")
    check("SLUG=" in sy, "sync loop derives a slug from the remote dir it covers")
    # --- LESSON (2026-07-27): a while-true with no liveness check OUTLIVES the pod it
    # syncs. 26 loops retried a terminated host for ~21h (ssh exit 255). "No new files"
    # and "cannot reach host" must not look the same.
    check("RC=$?" in sy and 'if [ "$RC" -ne 0 ]' in sy,
          "sync loop distinguishes ssh FAILURE from an empty listing")
    check("FAIL_LIMIT" in sy and "exit 1" in sy,
          "sync loop gives up and exits non-zero once the host is unreachable")
    # Verified behaviourally against a genuinely dead host: exits rc=1 after
    # SYNC_FAIL_LIMIT consecutive failures instead of timing out.
    check(au.SYNCED_D == "/workspace/.synced.d",
          "both sides agree on the per-directory sentinel directory")
    # --- LESSON (2026-10-20): the loop was FLAT. `ls -1` listed per-run SUBDIRECTORIES,
    # `scp` (no -r) failed on them into /dev/null, the loop still printed "pulled 4 new" and
    # then TOUCHED THE SENTINEL - telling the watchdog GLBs were safe that never left the pod.
    check("ls -1 $REMOTE" not in sy and "find " in sy and "-type f" in sy,
          "sync loop lists files RECURSIVELY (outputs live in per-run subdirectories)")
    check("COPY_OK" in sy and "PIPESTATUS" in sy,
          "sync loop checks the copy's exit status before claiming a pull")
    # Behavioural run against a live pod crashed: `[ "${PIPESTATUS[0]}" = 0 ] && [ "${PIPESTATUS[1]}" ...`
    # reads a PIPESTATUS the first `[` already overwrote -> "unbound variable" under set -u.
    check('ST=("${PIPESTATUS[@]}")' in sy and "${PIPESTATUS[1]}" not in sy,
          "PIPESTATUS is captured into an array immediately, never read twice")
    i_touch = sy.find("touch /workspace/.synced.d/$SLUG")
    check(i_touch > 0 and "if [ \"$COPY_OK\" = 1 ]" in sy[:i_touch],
          "sentinel is touched ONLY after every remote file is verified present locally")
    check("%s %P" in sy, "sync loop compares SIZES, so a file pulled mid-write is re-pulled")

    # --- LESSON: the old 'use managed, not pods' verdict was disproven.
    check("plain pods work" in readme.lower(),
          "docs leads with the corrected verdict (plain pods work)")
    check("LoadWanVideoT5TextEncoder" in readme,
          "docs records that the serverless-only missing node works on a plain pod")

    # --- LESSON (2026-07-25): a GENERAL skill stored under <repo>/.claude/skills is
    # DIRECTORY-SCOPED: it only loads once a file-level tool touches that subtree, so it is
    # unreachable from other projects. General capability => install at USER level.
    skill = io.open(os.path.join(ROOT, "skills", "remote-comfy", "SKILL.md"), encoding="utf-8").read()
    check(skill.startswith("---\nname: remote-comfy\n") and "\ndescription: " in skill,
          "skill has the frontmatter Claude Code needs to discover it")
    check(os.path.exists(os.path.join(ROOT, "scripts", "install-skill.sh")),
          "install-skill.sh deploys the skill to the USER level (~/.claude/skills)")
    check("REMOTE_COMFY_HOME" in skill,
          "SKILL.md resolves tools via REMOTE_COMFY_HOME, not a hardcoded checkout path")
    for tool in ("pod_ctl.py", "autostop.py", "comfy_client.py"):
        check(os.path.exists(P(tool)), "toolkit ships %s" % tool)
    check("python runpod/pod_ctl.py" not in readme,
          "canonical run does NOT depend on a private project repo path")

    # --- STANDING RULE (2026-07-26): research the latest models BEFORE testing.
    # A 3-way bake-off was run on FLUX.1-era models while FLUX.2 (Nov 2025) already
    # shipped the exact multi-reference capability under test.
    checker = P("check_latest_models.py")
    check(os.path.exists(checker), "check_latest_models.py ships with the toolkit (the STEP ZERO tool)")
    if os.path.exists(checker):
        src_c = io.open(checker, encoding="utf-8").read()
        check("huggingface.co/api/" in src_c,
              "model check queries the live HF API (empirical, not from training data)")
        check("lastModified" in src_c and "downloads" in src_c,
              "model check sorts by BOTH recency and adoption (newest != best)")
    check("STEP ZERO" in readme and "check_latest_models.py" in readme,
          "docs leads with the STEP ZERO research rule and names the tool")
    check("FLUX.2" in readme,
          "docs records the concrete miss that motivated the rule")

    # --- LESSON: rented boxes are EPHEMERAL. Outputs must stream to the laptop.
    sync = P("sync-outputs.sh")
    check(os.path.exists(sync), "sync-outputs.sh ships with the skill (pod storage is scratch)")
    if os.path.exists(sync):
        ssrc = io.open(sync, encoding="utf-8").read()
        check("while true" in ssrc and "scp" in ssrc, "sync loops and copies back continuously")
        # match real deletion syntax; the script's own comment says it never deletes
        bad_del = ("rm -", "--delete", "unlink ", "shutil.rmtree")
        check(not any(b in ssrc for b in bad_del), "sync NEVER deletes local artifacts")
    check("POD STORAGE IS SCRATCH" in readme, "docs warns that un-synced pod output can vanish")
    check("cc>=8.9" in readme and ("L40S" in readme or "RTX 6000 Ada" in readme),
          "docs says pick the CHEAPEST tier meeting the fp8 constraint, not the top tier")

    check("STOP/START DISCARDS THE CONTAINER DISK" in readme,
          "docs warns pip/apt are lost on resume (only /workspace survives)")

    # --- LESSON: the provisioning ORDER is where the failures came from. Encode it.
    prov_path = P("provision-comfyui.sh")
    check(os.path.exists(prov_path), "provision-comfyui.sh ships with the skill")
    prov = io.open(prov_path, encoding="utf-8").read() if os.path.exists(prov_path) else ""

    # torch trio together — bumping torch alone breaks ComfyUI's torchaudio import
    import re
    m = re.search(r"pip install[^\n]*\btorch==", prov)
    line = prov[m.start():prov.find("\n", m.start())] if m else ""
    check(all(k in line for k in ("torch==", "torchvision==", "torchaudio==")),
          "torch/torchvision/torchaudio are upgraded in ONE pip command")
    imp = re.search(r"^import .*\btorch\b.*$", prov, re.M)
    impline = imp.group(0) if imp else ""
    check(all(m in impline for m in ("torch", "torchvision", "torchaudio")),
          "all three are import-verified before ComfyUI launches")
    check("STAGE=/workspace" in prov and "--local-dir \"$STAGE\"" in prov,
          "HF downloads stage on the VOLUME, not the ~40GB container overlay")
    check("/tmp/d" not in prov, "no leftover /tmp staging (a 35GB model silently MISSes there)")
    # ORDER: custom nodes can re-resolve torch and swap the CUDA variant, so the pin
    # must come AFTER node installs (2026-07-26).
    i_nodes, i_torch = prov.find("custom_nodes"), prov.find("torch==")
    check(0 <= i_nodes < i_torch, "torch trio is pinned AFTER custom-node installs")
    check("CUDA VARIANT MISMATCH" in prov,
          "provision asserts torch/vision/audio CUDA variants AGREE (not a specific variant)")
    check("libsamplerate0-dev" in prov and "portaudio19-dev" in prov,
          "audio custom-node system deps installed before node install")
    check("enable_gqa" in prov, "provision explains WHY torch must be >=2.5 (Qwen enable_gqa)")

    # the watchdog must not kill a provision; the lock must always be released
    check("touch \"$LOCK\"" in prov or "touch $LOCK" in prov,
          "provision takes the /workspace/.busy lock before long downloads")
    check("trap 'rm -f \"$LOCK\"' EXIT" in prov,
          "lock is released on EXIT (a stuck lock would keep a pod billing forever)")

    # SIGHUP + readiness
    check("nohup setsid" in prov and "disown" in prov,
          "ComfyUI launches with nohup setsid ... disown (survives SSH close)")
    check("system_stats" in prov and "COMFY_READY" in prov,
          "provision waits for ComfyUI to actually answer before declaring done")
    # --- LESSON (2026-10-20, ~75 min of idle 4090): current ComfyUI pins comfy-kitchen, whose
    # custom ops use `list[int]` annotations torch 2.6's infer_schema rejects -> ComfyUI dies on
    # import. Provision still printed PROVISION_DONE: its readiness loop used curl (absent on the
    # pod image) and fell through on timeout. The watchdog then HELD the dead pod as "busy".
    tv = re.search(r"\btorch==(\d+)\.(\d+)", prov)
    check(tv is not None and (int(tv.group(1)), int(tv.group(2))) >= (2, 7),
          "torch pin is >= 2.7 (comfy-kitchen custom ops need PEP 585 list[int] schemas)")
    check("import comfy_kitchen" in prov, "provision import-verifies comfy_kitchen before launch")
    launch = prov[prov.find("# --- launch"):]
    check("curl -" not in launch and "urllib.request" in launch,
          "readiness is polled with python, not curl (the pod image has no curl)")
    check('echo "PROVISION_FAILED' in launch and "exit 1" in launch
          and launch.find('[ "$READY" = 1 ]') < launch.find('echo "PROVISION_DONE"'),
          "PROVISION_DONE only after a verified ready; otherwise PROVISION_FAILED + exit 1")

    # loader-type distinction (all-in-one checkpoint vs bare UNET)
    check("CheckpointLoaderSimple" in prov and "UNETLoader" in prov,
          "provision records which model sets are all-in-one vs bare UNET")

    # LESSON (2026-10-19): Comfy's native image->3D template (3d_pixal3d_trellis2_image_to_model)
    # needs BOTH diffusion models (its switch node must be able to load either) plus MoGe and
    # BiRefNet, which live in OTHER repos. A set that ships only the obvious files fails late.
    m3d = re.search(r"^\s*3d\)(.*?);;", prov, re.M | re.S)
    block = m3d.group(1) if m3d else ""
    need = ["pixal3d_bf16.safetensors", "trellis_2_bf16.safetensors", "trellis_2_shape_vae_bf16.safetensors",
            "trellis_2_texture_vae_bf16.safetensors", "dino_v3_L_naf_fp32.safetensors",
            "moge_2_vitl_normal_fp16.safetensors", "birefnet.safetensors"]
    check(m3d is not None and all(f in block for f in need),
          "3d set ships every file the native Pixal3D/TRELLIS.2 template loads (both models, MoGe, BiRefNet)")
    check("models/background_removal" in block and "models/geometry_estimation" in block,
          "3d set puts BiRefNet/MoGe in the folders the native loaders read")

    # doc-level: the stranding + torchaudio traps must stay written down
    check("not enough free GPUs" in readme.lower() or "strand" in readme.lower(),
          "docs warns that stopping a pod can strand it (per-HOST stock)")
    check("libtorchaudio" in readme or "torchaudio" in readme,
          "docs warns that a torch bump without torchaudio bricks ComfyUI")

    # --- LESSON (2026-07-26): AUDIO nodes need apt packages the image lacks,
    # and RVC misreports a missing ffmpeg as an F0/rmvpe failure (cost ~1h chasing rmvpe.pt).
    check("ffmpeg" in prov,
          "provision installs ffmpeg (RVC shells out to it; absence is misreported as an F0 failure)")
    check("libsamplerate0-dev" in prov and "portaudio19-dev" in prov,
          "provision installs the audio dev libs TTS engines require")

    # --- LESSON: a resume loses the container disk; only /workspace survives.
    check("container disk" in readme.lower(),
          "docs warns that stop/start discards pip+apt (only /workspace survives)")

    # --- LESSON: block-buffered stdout made a live job look dead; the queue is server-side.
    check("python3 -u" in readme,
          "docs warns about block-buffered stdout hiding a live job")

    # --- LESSON: node registration is not engine installation.
    check("REGISTERED" in readme.upper() and "INSTALLED" in readme.upper(),
          "docs warns a registered node class may have no working engine behind it")

    # --- LESSON: MooseFS-backed /workspace is slow; a boot that looks hung is not.
    check("MooseFS" in readme or "request_wait_answer" in readme,
          "docs explains the MooseFS slow-import / apparently-hung boot")

    # --- LESSON (2026-07-26): a per-GPU instance that booted while a stale process
    # squatted VRAM loads the model PARTIALLY and runs ~4x slower, with NO error and
    # 100% GPU utilisation. Only the "loaded partially" log line reveals it.
    gpuload_p = P("check-gpu-load.sh")
    check(os.path.exists(gpuload_p),
          "check-gpu-load.sh exists (detects partially-loaded per-GPU instances)")
    if os.path.exists(gpuload_p):
        gl = io.open(gpuload_p, encoding="utf-8").read()
        check("nvidia-smi" in gl,
              "check-gpu-load.sh tells you how to confirm no process still holds VRAM")
        # LESSON (2026-10-23, live 2xA40 on ComfyUI 0.42.0): ComfyUI stopped printing
        # "loaded completely/partially", so the old check could never pass and blamed CPU
        # streaming that was not happening. Speed parity is the signal now; run the real
        # script over canned "<log>|<loadline>|<rate>" input.
        import subprocess

        def gpuload(lines):
            f = os.path.join(tempfile.mkdtemp(), "in.txt")
            io.open(f, "w", newline="\n").write("\n".join(lines) + "\n")
            env = dict(os.environ, CHECK_GPU_LOAD_INPUT=f.replace("\\", "/"))
            try:
                return subprocess.run(["bash", gpuload_p.replace("\\", "/"), "-", "-"], env=env,
                                      capture_output=True, text=True, timeout=30).returncode
            except Exception:
                return None
        check(gpuload(["g0||1.18it/s", "g1||1.25it/s"]) == 0,
              "matched speeds on new-style logs (no 'loaded completely' line) PASS")
        check(gpuload(["g0||23.8s/it", "g1||7.8s/it"]) == 1,
              "the 2026-07-26 incident (23.8 vs 7.8 s/it) is flagged SLOW")
        check(gpuload(["g0||7.8s/it", "g1|loaded partially; 11781 MB offloaded|8.0s/it"]) == 1,
              "an old-style 'loaded partially' line still fails")
        check(gpuload(["g0||", "g1||1.2it/s"]) == 1,
              "an instance with no sampling rate yet is NOT a pass")
    check("loaded partially" in readme,
          "docs warns that a VRAM squatter silently halves throughput")

    # --- LESSON (2026-07-26): the sharded launcher is where these lessons actually run.
    # Keeping it on an ephemeral pod means re-deriving them after every re-provision.
    launch_p = P("launch-sharded.sh")
    check(os.path.exists(launch_p), "launch-sharded.sh exists (one ComfyUI per GPU)")
    if os.path.exists(launch_p):
        ls = io.open(launch_p, encoding="utf-8").read()
        # A literal 'main.py --listen' stops matching as soon as a flag is added before it.
        check("main\\.py.*--listen" in ls,
              "kill pattern is a regex that survives inserted flags")
        check("--disable-cuda-malloc" in ls,
              "native allocator (async pool hides free VRAM -> partial model load)")
        # The lock must be taken BEFORE the long work, not after.
        i_busy, i_spawn = ls.find("touch /workspace/.busy"), ls.find("nohup setsid python main.py")
        check(0 <= i_busy < i_spawn, ".busy is held BEFORE any long-running work starts")
        # setsid children are invisible to pgrep for a moment; polling immediately drops
        # the lock while the batch is still queued.
        i_sleep, i_wait = ls.find("sleep 90"), ls.find("while pgrep")
        check(0 <= i_sleep < i_wait, "waits before the 'until my children exit' poll loop")
        check("python3 -u" in ls, "harness runs unbuffered (a live job looked dead once)")
        check("system_stats" in ls and "== 200" in ls,
              "waits for HTTP 200 readiness, not a fixed sleep")
        # The pod image has no curl: a curl queue-clear silently no-ops and a curl
        # readiness loop never sees 200 (the same bug provision had, 2026-10-20).
        check("curl " not in ls, "launcher makes no curl calls (absent from the pod image)")
        # The lock became a heartbeat (TTL) but the launcher still touched it ONCE, so any
        # batch longer than the TTL lost its protection once shard 0 (the only queue the
        # watchdog polls) drained.
        wl = re.search(r"^while pgrep .*$", ls, re.M)
        check(wl is not None and "touch /workspace/.busy" in wl.group(0),
              "launcher refreshes the .busy heartbeat inside its wait loop")
        # Stale server-side prompts outlive the harness; a relaunch with new parameters
        # renders at the OLD ones until they drain.
        i_clear, i_kill = ls.find('"clear":true'), ls.find("pkill -f 'main")
        check(0 <= i_clear < i_kill,
              "clears the server-side queue BEFORE killing the servers")
        check("/interrupt" in ls, "interrupts the in-flight prompt too")
        # SELF-MATCH: the launcher's own argv contains the harness path, so a bare
        # `pkill/pgrep -f <harness>.py` matches the launcher itself. In the kill line that
        # made the script commit suicide silently; in the wait loop it made the condition
        # permanently true, so it spun forever holding .busy while the job was dead.
        check("pkill -f \"$(basename \"$HARNESS\")\"" not in ls,
              "kill line does not self-match the launcher's own argv")
        check("while pgrep -f \"$(basename \"$HARNESS\")\"" not in ls,
              "wait loop does not self-match the launcher's own argv")
        check(ls.count('python3 -u .*$(basename "$HARNESS")') >= 2,
              "both the kill and the wait match the PYTHON invocation, not the filename")

    # --- LESSONS from the 2026-07-26 cross-session RunPod post-mortem ----------------
    # Each cost real time or money in a transcript. Prose rots; these fail loudly if
    # someone trims the trap out of SKILL.md.
    check("LIES ON A NETWORK VOLUME" in readme,
          "docs warns df reports the shared MooseFS pool, not your quota")
    check("100GB" in readme and "resized" in readme,
          "docs says size the volume up front (it cannot be resized)")
    check("huggingface-cli" in readme and "hf download" in readme,
          "docs records the pod CLI is `hf`, not the dead huggingface-cli")
    check("COMPLETION MARKER IS NOT COMPLETION" in readme,
          "docs warns a done-marker can print on total failure")
    check("502" in readme and "404" in readme,
          "docs decodes proxy status codes (502 during load is not a crash)")
    check("User-Agent" in readme,
          "docs warns the proxy filters by User-Agent and gates writes")
    check("1010" in readme,
          "docs records GraphQL is Cloudflare-blocked (REST v1 is the API)")
    # LESSON (2026-10-19): Cloudflare now ALSO answers 1010 on rest.runpod.io for urllib's
    # default UA. `pod_ctl list` died with "API GET /pods: error code: 1010"; create/conn
    # would have failed mid-session. Every REST request must send a browser User-Agent.
    ctl = io.open(P("pod_ctl.py"), encoding="utf-8").read()
    m_req = re.search(r"def req\(.*?\n(?=def )", ctl, re.S)
    check(m_req is not None and "User-Agent" in m_req.group(0),
          "pod_ctl REST req() sends a browser User-Agent (Cloudflare 1010s urllib's default)")
    check("LACK TOOLS YOU ASSUME" in readme,
          "docs warns curl/tmux/ffmpeg may be absent from the pod image")
    check("SSH Public Keys" in readme,
          "docs records SSH keys are injected at boot from ACCOUNT settings")
    check("host-lottery" in readme,
          "docs keeps uptime as the host-lottery check while banning it for own-CPU")
    check("NO CAPACITY, NOT BAD SYNTAX" in readme,
          "docs records that a create 500 means no capacity")
    check("gpuTypeId" in readme and "displayName" in readme,
          "docs records the create/availability id-vocabulary mismatch")
    check("VIDEO-SHAPED" in readme,
          "docs warns its own GPU table is video-shaped (audio overspends ~9x)")
    check("ACCOUNT-WIDE BALANCE" in readme,
          "docs warns another session's pod can strand yours via account balance")
    check("ISOLATED PYTHON RUNTIME" in readme,
          "docs warns a node pack may ignore the system torch entirely")
    check("setuptools" in readme and "pkg_resources" in readme,
          "docs records the missing-setuptools build chicken-and-egg")
    check("CVE-2025-32434" in readme,
          "docs records the transformers 5.x torch.load guard blocking .bin models")
    check("git clone --quiet" in readme,
          "docs says clone quietly so the log stays readable")
    # LESSON (2026-11-15): the docs said it, the provisioner did not; ComfyUI's clone wrote
    # ~1,300 progress updates into prov.log. Check the code, not just the prose.
    clones = re.findall(r"git clone[^\n]*", io.open(P("provision-comfyui.sh"), encoding="utf-8").read())
    check(clones and all("--quiet" in c for c in clones),
          "every git clone in provision-comfyui.sh is --quiet %s" % [c for c in clones if "--quiet" not in c])
    check("MEASURE BEFORE YOU PROJECT" in readme,
          "docs warns runtime estimates were wrong 2-5x, twice")
    check("displayable" in readme or "4.2 MP" in readme,
          "docs warns about rendering far above the delivery resolution")

    # --- EXAMPLES: the harness contract launch-sharded.sh depends on, checked offline.
    ex = os.path.join(ROOT, "examples")
    wf = json.load(open(os.path.join(ex, "workflows", "flux1_dev_txt2img.json")))
    links = [v for n in wf.values() for v in n["inputs"].values() if isinstance(v, list)]
    check(all(str(l[0]) in wf for l in links),
          "example workflow: every link points at a node that exists")
    ck = [k for k, n in wf.items() if n["class_type"] == "CheckpointLoaderSimple"]
    check(len(ck) == 1 and sorted({l[1] for l in links if l[0] == ck[0]}) == [0, 1, 2],
          "example workflow reads MODEL/CLIP/VAE as outputs 0/1/2 of ONE all-in-one loader")
    check(any(n["class_type"] == "SaveImage" for n in wf.values()),
          "example workflow has a terminal output node (else prompt_no_outputs)")
    hx = load("batch_harness", os.path.join(ex, "batch_harness.py"))
    out = hx.apply(wf, {"2.text": "x", "6.seed": 7})
    check(out["2"]["inputs"]["text"] == "x" and wf["2"]["inputs"]["text"] != "x",
          "harness overrides inputs on a COPY, never mutating the shared workflow")
    jobs = json.load(open(os.path.join(ex, "jobs.json")))
    check(all(os.path.exists(os.path.join(ex, j["workflow"])) for j in jobs),
          "every example job names a workflow file that exists")
    # Resume: with every job of shard 0 already on disk, the harness must finish WITHOUT
    # contacting ComfyUI. The stub records contact and fails fast (the real client would
    # sit in wait_ready for 15 min, turning a regression into a hang instead of a FAIL).
    contacted = []

    class _NoComfy:
        def __init__(self, url):
            contacted.append(url)
            raise RuntimeError("harness contacted ComfyUI")
    real_comfy, hx.Comfy = hx.Comfy, _NoComfy
    tout = tempfile.mkdtemp()
    for i, j in enumerate(jobs):
        if i % 2 == 0:
            open(os.path.join(tout, j["id"] + "_rc_00001_.png"), "w").close()
    try:
        rc = hx.main(["--shard", "0", "--of", "2",
                      "--jobs", os.path.join(ex, "jobs.json"), "--out", tout])
    except RuntimeError:
        rc = None
    finally:
        hx.Comfy = real_comfy
    check(rc == 0 and not contacted,
          "harness skips work already on disk (a relaunch resumes, not redoes)")
    # ...and shard 1 (one job, not on disk) DOES go to ComfyUI: sharding is index % of.
    hx.Comfy = _NoComfy
    try:
        hx.main(["--shard", "1", "--of", "2", "--jobs", os.path.join(ex, "jobs.json"), "--out", tout])
    except RuntimeError:
        pass
    finally:
        hx.Comfy = real_comfy
    check(len(contacted) == 1, "shard 1 of 2 picks up its own unfinished job")
    hsrc = io.open(os.path.join(ex, "batch_harness.py"), encoding="utf-8").read()
    check(all(f in hsrc for f in ('"--comfy"', '"--shard"', '"--of"')),
          "harness accepts the --comfy/--shard/--of contract launch-sharded.sh passes")

    # Every example graph must run on a pod provisioned by this repo: each model file it loads
    # is downloaded by some provision set (a graph naming a file no set fetches fails on the pod,
    # after the rent has started). Every job list's overrides must hit a real node and input.
    prov_files = set(os.path.basename(m) for m in re.findall(r"^\s*dl \S+ (\S+) ", prov, re.M))
    file_inputs = ("unet_name", "clip_name", "vae_name", "lora_name", "ckpt_name",
                   "style_model_name", "bg_removal_name", "model_name")
    wfdir = os.path.join(ex, "workflows")
    graphs = {}
    for name in sorted(os.listdir(wfdir)):
        if name.endswith(".json"):
            graphs["workflows/" + name] = json.load(io.open(os.path.join(wfdir, name), encoding="utf-8"))
    missing = sorted({(g, v) for g, wfx in graphs.items() for n in wfx.values()
                      for k, v in n["inputs"].items() if k in file_inputs and v not in prov_files})
    check(len(graphs) >= 5 and not missing,
          "every model file an example graph loads is downloaded by a provision set %s" % (missing,))
    dangling = sorted({(g, k) for g, wfx in graphs.items() for n in wfx.values()
                       for k, v in n["inputs"].items() if isinstance(v, list) and str(v[0]) not in wfx})
    check(not dangling, "every link in every example graph points at a node that exists %s" % (dangling,))
    bad_sets = []
    for jf in sorted(f for f in os.listdir(ex) if f.startswith("jobs") and f.endswith(".json")):
        for j in json.load(io.open(os.path.join(ex, jf), encoding="utf-8")):
            wfx = graphs.get(j["workflow"])
            if wfx is None:
                bad_sets.append((jf, j["id"], j["workflow"]))
                continue
            for key in j.get("set", {}):
                node, field = key.split(".", 1)
                if node not in wfx or field not in wfx[node]["inputs"]:
                    bad_sets.append((jf, j["id"], key))
    check(not bad_sets, "every job's overrides name a node and input its graph has %s" % (bad_sets,))

    # --- CATALOGUE: model lists rot fastest, so the catalogue is data with checks, not prose.
    ct = load("catalog", os.path.join(ROOT, "remote_comfy", "catalog.py"))
    good = {"checked_on": "2026-10-01", "workflows": [{"name": "w", "url": "https://x"}],
            "models": [{"id": "m1", "name": "M1", "task": "t2i", "hf_repo": "org/m1",
                        "license": "apache-2.0", "comfy_support": "native", "pick_when": "p",
                        "files": [{"repo": "org/m1", "path": "split_files/vae/a.safetensors",
                                   "comfy_dir": "vae", "size_gb": 1.0}]}]}
    import datetime as _dt
    today = _dt.date(2026, 10, 23)
    check(ct.validate(good, today) == [], "catalogue validator accepts a well-formed entry")
    import copy as _cp
    def bad(mut):
        c = _cp.deepcopy(good); mut(c); return ct.validate(c, today)
    check(bad(lambda c: c["models"][0].update(task="video")) != [], "validator rejects an unknown task")
    check(bad(lambda c: c["models"].append(dict(c["models"][0]))) != [], "validator rejects duplicate ids")
    check(bad(lambda c: c["models"][0]["files"][0].update(comfy_dir="../../etc")) != [],
          "validator rejects a file destination that escapes models/")
    check(bad(lambda c: c["models"][0].update(comfy_support="custom-node")) != [],
          "custom-node support must name its node repo")
    check(bad(lambda c: c.update(checked_on="2026-05-01")) != [],
          "a catalogue older than %d days fails validation (it has rotted)" % ct.STALE_DAYS)
    fake = {"org/m1": {"siblings": [{"rfilename": "split_files/vae/a.safetensors"}]}}
    check(ct.verify(good, fetch=fake.get) == [], "verify passes when repo and file resolve")
    moved = {"org/m1": {"siblings": [{"rfilename": "vae/a.safetensors"}]}}
    check(any("moved" in p for p in ct.verify(good, fetch=moved.get)),
          "verify catches a file that moved between repo root and split_files/")
    check(any("not found" in p for p in ct.verify(good, fetch={}.get)), "verify catches a vanished repo")
    check(ct.dl_lines(good, ["m1"]) == ["org/m1 split_files/vae/a.safetensors models/vae"],
          "--dl emits the '<repo> <path> <dest>' lines provision reads")
    # --dl selection: exclusion keeps shared files. A keep-filter ("--only int8") dropped
    # FLUX 3's VAE because its filename carries no precision tag (2026-10-23).
    multi = _cp.deepcopy(good)
    multi["models"][0]["files"] = [
        {"repo": "o/m", "path": "dm/m-int8.st", "comfy_dir": "diffusion_models"},
        {"repo": "o/m", "path": "dm/m-bf16.st", "comfy_dir": "diffusion_models"},
        {"repo": "o/m", "path": "vae/ae.st", "comfy_dir": "vae"}]
    got = ct.dl_lines(multi, ["m1"], skip=["bf16"])
    check(len(got) == 2 and any("vae/ae.st" in g for g in got) and not any("bf16" in g for g in got),
          "--dl --skip drops the unwanted precision but keeps shared files like the VAE")
    node = _cp.deepcopy(good)
    node["models"][0].update(comfy_support="custom-node", custom_node_repo="https://github.com/x/y",
                             files=[{"repo": "o/m", "path": "w.pt", "comfy_dir": None}])
    check(ct.validate(node, today) == [], "custom-node entries may list node-fetched files (comfy_dir null)")
    try:
        ct.dl_lines(node, ["m1"]); refused = False
    except KeyError:
        refused = True
    check(refused, "--dl refuses weights a custom node fetches itself (nowhere correct to put them)")
    nohf = _cp.deepcopy(good); del nohf["models"][0]["hf_repo"]
    check(ct.validate(nohf, today) != [], "an entry needs hf_repo or comfy_repo")
    nohf["models"][0]["comfy_repo"] = "Comfy-Org/x"
    check(ct.validate(nohf, today) == [], "a Comfy-only repackage (no upstream HF repo) is valid")

    # The real catalogue ships valid, and its rendered doc matches it (docs cannot drift).
    real = ct.load()
    errs = ct.validate(real)
    check(not errs, "catalog/catalog.json validates %s" % (errs[:3] or ""))
    check(set(ct.TASKS) <= {m["task"] for m in real["models"]},
          "catalogue covers every core task")
    md = io.open(os.path.join(ROOT, "docs", "models.md"), encoding="utf-8").read()
    check(md == ct.markdown(real),
          "docs/models.md is regenerated from the JSON (run catalog.py --write-docs)")
    # provision reads the catalogue's extra-models.txt, and a download that reads stdin must
    # not swallow the rest of the list (the dl stub below deliberately drains stdin).
    blk = prov[prov.find("EXTRA=/workspace/extra-models.txt"):prov.find('rm -rf "$STAGE"')]
    check("while read -r repo path dest" in blk and "</dev/null" in blk,
          "provision installs catalogue extras, with dl's stdin detached")
    if blk:
        import subprocess
        tx = tempfile.mkdtemp()
        lst = os.path.join(tx, "x.txt")
        io.open(lst, "w", newline="\n").write("# comment\norg/a p/a.st models/vae\n\norg/b b.st models/loras\n")
        script = ('dl(){ cat >/dev/null; echo "DL $1 $2 $3"; }\n'
                  + blk.replace("/workspace/extra-models.txt", lst.replace("\\", "/")))
        try:
            r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
            got = r.stdout.split("\n")
        except Exception as e:
            got = [str(e)]
        check([g for g in got if g] == ["DL org/a p/a.st models/vae", "DL org/b b.st models/loras"],
              "provision extras loop downloads every line even when dl reads stdin")

    # --- Console output must be ASCII: a Windows console (cp1252) printed the em dash in
    # pod_ctl's missing-key message as a garbage glyph (2026-10-23, fresh-clone test).
    bad_out = []
    for f in sorted(os.listdir(os.path.join(ROOT, "remote_comfy"))):
        if f.endswith(".py"):
            for i, l in enumerate(io.open(os.path.join(ROOT, "remote_comfy", f), encoding="utf-8"), 1):
                if re.search(r"\b(print|sys\.exit|log|input)\(", l) and any(ord(c) > 127 for c in l):
                    bad_out.append("%s:%d" % (f, i))
    check(not bad_out, "user-facing output strings are ASCII %s" % (bad_out[:5] or ""))

    # --- PUBLIC REPO HYGIENE: no keys, no absolute home paths in anything we ship.
    # Proven able to fail: a planted "rpa_" + 24 chars in a scratch file was caught.
    leak = re.compile(r"(rpa_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{20,}"
                      r"|[A-Z]:\\Users\\[A-Za-z]|/home/[a-z]+/|/Users/[A-Za-z]+/)")
    hits = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__", ".venv")]
        for f in fn:
            if f.endswith((".py", ".sh", ".md", ".json", ".toml", ".yml", ".example", ".txt")):
                p = os.path.join(dp, f)
                for i, line in enumerate(io.open(p, encoding="utf-8", errors="replace"), 1):
                    if leak.search(line):
                        hits.append("%s:%d" % (os.path.relpath(p, ROOT), i))
    check(not hits, "no API keys or absolute user paths in shipped files %s" % (hits[:5] or ""))

    # LESSON (2026-11-20, timed live): `ssh pod 'nohup setsid job & disown; echo ok'` returned
    # after 3 s with the job's output redirected and after 28 s (the job's whole life) without:
    # a backgrounded job that keeps stdout holds the ssh channel open. Every launch line we
    # ship or show, prose included, carries its redirects, because readers copy them.
    bare = []
    shipped = ["AGENTS.md"] + [os.path.join(d, f) for d in ("docs", "pod", "local", "scripts", "remote_comfy")
                               if os.path.isdir(os.path.join(ROOT, d))
                               for f in sorted(os.listdir(os.path.join(ROOT, d)))
                               if f.endswith((".md", ".sh", ".py"))] + ["skills/remote-comfy/SKILL.md"]
    for rel in shipped:
        text = io.open(os.path.join(ROOT, rel), encoding="utf-8").read().replace("\\\n", " ")
        for i, line in enumerate(text.splitlines(), 1):
            if "& disown" in line and not ("2>&1" in line and "</dev/null" in line):
                bare.append("%s: %s" % (rel, line.strip()[:60]))
    check(not bare, "every `& disown` launch redirects stdout, stderr and stdin off the ssh channel %s"
          % (bare[:4] or ""))

    print("\n%s" % ("FAILED: " + "; ".join(FAIL) if FAIL else "ALL PASS"))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
