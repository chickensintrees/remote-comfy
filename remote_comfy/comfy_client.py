#!/usr/bin/env python3
"""Minimal ComfyUI HTTP client — drive a LOCAL or REMOTE ComfyUI identically.

Remote = a rented GPU reached via SSH `-L` tunnel or the RunPod proxy URL; nothing in
here cares which. See the `remote-comfy` skill for renting/pausing the box.

  from comfy_client import Comfy
  c = Comfy("http://127.0.0.1:8189")
  c.wait_ready()
  name = c.upload("scene.jpg")            # -> filename usable by LoadImage
  imgs = c.run(workflow_dict)             # -> [(filename, bytes), ...]

  c = connect("cloud")                    # Comfy Cloud: same calls, key COMFY_CLOUD_API_KEY

Stdlib only (works on the pod too). Every call retries transient errors.
"""
import json, mimetypes, os, time, urllib.error, urllib.parse, urllib.request, uuid


class Comfy:
    def __init__(self, base="http://127.0.0.1:8188", timeout=60):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.cid = uuid.uuid4().hex

    # ---- transport ---------------------------------------------------------
    def _open(self, req, timeout=None, tries=5):
        last = None
        for i in range(tries):
            try:
                return urllib.request.urlopen(req, timeout=timeout or self.timeout)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
                time.sleep(2 * (i + 1))
        raise last

    def get(self, path, timeout=None):
        return json.loads(self._open(urllib.request.Request(self.base + path), timeout).read())

    def post(self, path, data, timeout=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"})
        return json.loads(self._open(req, timeout).read())

    # ---- helpers -----------------------------------------------------------
    def wait_ready(self, minutes=15):
        """ComfyUI takes a while to import custom nodes; unreachable != broken."""
        deadline = time.time() + minutes * 60
        while time.time() < deadline:
            try:
                self.get("/system_stats", timeout=10)
                return True
            except Exception:
                time.sleep(5)
        raise RuntimeError("ComfyUI not ready after %d min" % minutes)

    def nodes(self):
        return self.get("/object_info", timeout=180)

    def has(self, *names):
        info = self.nodes()
        return {n: (n in info) for n in names}

    def upload(self, path, subfolder=""):
        """multipart upload -> returns the filename LoadImage should reference."""
        boundary = "----comfy" + uuid.uuid4().hex
        fn = os.path.basename(path)
        mime = mimetypes.guess_type(fn)[0] or "image/png"
        parts = []
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
                      "Content-Type: %s\r\n\r\n" % (boundary, fn, mime)).encode())
        parts.append(open(path, "rb").read())
        parts.append(("\r\n--%s\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
                      % boundary).encode())
        if subfolder:
            parts.append(("--%s\r\nContent-Disposition: form-data; name=\"subfolder\"\r\n\r\n%s\r\n"
                          % (boundary, subfolder)).encode())
        parts.append(("--%s--\r\n" % boundary).encode())
        body = b"".join(parts)
        req = urllib.request.Request(self.base + "/upload/image", data=body,
                                     headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        d = json.loads(self._open(req, 120).read())
        return (d.get("subfolder") + "/" + d["name"]) if d.get("subfolder") else d["name"]

    def run(self, workflow, wait_min=20):
        """Queue an API-format workflow, wait, return [(filename, bytes)]."""
        pid = self.post("/prompt", {"prompt": workflow, "client_id": self.cid})["prompt_id"]
        deadline = time.time() + wait_min * 60
        while time.time() < deadline:
            time.sleep(3)
            h = self.get("/history/" + pid, timeout=60)
            if pid not in h:
                continue
            entry = h[pid]
            st = (entry.get("status") or {})
            if st.get("status_str") == "error" or st.get("completed") is False and st.get("messages"):
                for m in st.get("messages", []):
                    if m and m[0] == "execution_error":
                        raise RuntimeError("ComfyUI error: %s" % json.dumps(m[1])[:400])
            outs = []
            for _, node in (entry.get("outputs") or {}).items():
                for im in node.get("images", []):
                    q = urllib.parse.urlencode({"filename": im["filename"],
                                                "subfolder": im.get("subfolder", ""),
                                                "type": im.get("type", "output")})
                    data = self._open(urllib.request.Request(self.base + "/view?" + q), 300).read()
                    outs.append((im["filename"], data))
            if outs:
                return outs
            if st.get("completed"):
                return []
        raise TimeoutError("workflow did not finish in %d min" % wait_min)


# ---- Comfy Cloud ---------------------------------------------------------------
# see: decisions/2026-11-20-comfy-cloud-backend.md (v2 job loop, v1 node list, live gaps)
CLOUD = "https://cloud.comfy.org"
# Cloudflare 1010'd urllib's default UA on RunPod's API; send a browser UA here too.
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"
DONE = ("succeeded", "failed", "canceled", "expired")


def cloud_key():
    k = (os.environ.get("COMFY_CLOUD_API_KEY") or "").strip()   # a pasted or piped key carries \r
    if k:
        return k
    try:
        import keyring
        k = keyring.get_password(os.environ.get("REMOTE_COMFY_CLOUD_KEYRING_SERVICE", "remote-comfy"),
                                 os.environ.get("REMOTE_COMFY_CLOUD_KEYRING_USER", "comfy-cloud"))
        if k:
            return k.strip()
    except Exception:
        pass
    raise SystemExit("no COMFY_CLOUD_API_KEY - export it, or store it with "
                     "`python -m keyring set remote-comfy comfy-cloud`")


class CloudError(Exception):
    def __init__(self, status, code, message):
        Exception.__init__(self, "Comfy Cloud HTTP %s %s: %s" % (status, code, message))
        self.status, self.code = status, code


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib re-sends every header on a redirect, the key included. Stop, and let the
    caller fetch the signed storage URL with no headers."""
    def redirect_request(self, *a, **k):
        return None


def _multipart(fields, file_field, filename, data, mime):
    """Plain fields first, the file LAST (v2 assets ignores fields after the file)."""
    b = "----remotecomfy" + uuid.uuid4().hex
    out = []
    for name, value in fields:
        out.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                    % (b, name, value)).encode())
    out.append(('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                'Content-Type: %s\r\n\r\n' % (b, file_field, filename, mime)).encode())
    out += [data, ("\r\n--%s--\r\n" % b).encode()]
    return b"".join(out), "multipart/form-data; boundary=" + b


class CloudComfy:
    """Comfy Cloud with the same calls as Comfy: wait_ready / nodes / has / upload / run.

    Jobs, outputs and uploads use the v2 API (Bearer); the node list is v1 only (X-API-Key).
    The key goes in a header and nowhere else: never a URL, never a storage redirect."""

    def __init__(self, base=CLOUD, key=None, timeout=60, poll=3):
        self.base = base.rstrip("/")
        self.host = urllib.parse.urlsplit(self.base).netloc
        self._key, self.timeout, self.poll = key, timeout, poll
        self._opener = urllib.request.build_opener(_NoRedirect)
        self._sleep = time.sleep

    def key(self):
        if not self._key:
            self._key = cloud_key()
        return self._key.strip()

    def _raw(self, req, timeout):
        """Every request goes through here (tests replace it)."""
        return self._opener.open(req, timeout=timeout)

    def _scrub(self, text):
        return str(text).replace(self.key(), "***") if self._key else str(text)

    def _call(self, method, url, body=None, headers=None, v1=False, raw=False, timeout=None, tries=4):
        if not url.startswith("http"):
            url = self.base + url
        h = {"User-Agent": UA}
        if urllib.parse.urlsplit(url).netloc == self.host:      # the key only ever goes to Comfy
            if v1:
                h["X-API-Key"] = self.key()
            else:
                h["Authorization"] = "Bearer " + self.key()
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        for i in range(tries):
            req = urllib.request.Request(url, data=body, method=method, headers=h)
            try:
                b = self._raw(req, timeout or self.timeout).read()
                return b if raw else (json.loads(b) if b.strip() else {})
            except urllib.error.HTTPError as e:
                loc = e.headers.get("Location") if e.headers else None
                if e.code in (301, 302, 303, 307, 308) and loc:
                    # signed storage URL: it carries its own authorization, so no headers
                    return self._call("GET", urllib.parse.urljoin(url, loc), raw=raw,
                                      timeout=timeout, tries=tries)
                text = e.read().decode("utf-8", "replace") if e.fp else ""
                try:
                    err = json.loads(text).get("error") or {}
                    code, msg = err.get("code"), err.get("message") or text
                except (ValueError, AttributeError):
                    code, msg = None, text
                if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                    ra = e.headers.get("Retry-After") if e.headers else None
                    self._sleep(float(ra) if ra and str(ra).isdigit() else 2 * (i + 1))
                    continue
                raise CloudError(e.code, code, self._scrub(msg)[:400])
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if i == tries - 1:
                    raise
                self._sleep(2 * (i + 1))

    def wait_ready(self, minutes=0):
        """No boot to wait for. Proves the key works: an unknown job is a 404, a bad key a 401."""
        try:
            self._call("GET", "/api/v2/jobs/00000000-0000-0000-0000-000000000000", tries=1)
        except CloudError as e:
            if e.status != 404:
                raise
        return True

    def nodes(self):
        return self._call("GET", "/api/object_info", v1=True, timeout=180)

    def has(self, *names):
        info = self.nodes()
        return {n: (n in info) for n in names}

    def upload(self, path, api="v2"):
        """v2 -> the core/ASSET reference that goes where LoadImage's filename would;
        v1 -> a plain filename. LoadImage took the v2 reference live on 2026-11-20."""
        fn = os.path.basename(path)
        mime = mimetypes.guess_type(fn)[0] or "application/octet-stream"
        data = open(path, "rb").read()
        if api == "v1":
            body, ctype = _multipart([("type", "input")], "image", fn, data, mime)
            d = self._call("POST", "/api/upload/image", body, {"Content-Type": ctype}, v1=True, timeout=300)
            return (d["subfolder"] + "/" + d["name"]) if d.get("subfolder") else d["name"]
        body, ctype = _multipart([("content_type", mime), ("file_path", fn)], "file", fn, data, mime)
        a = self._call("POST", "/api/v2/assets", body, {"Content-Type": ctype}, timeout=300)
        return {"__type": "core/ASSET",
                "info": {"id": a["id"], "hash": a.get("hash"), "file_path": a.get("file_path") or fn}}

    def run(self, workflow, wait_min=20):
        """Submit an API-format workflow, poll until done, return [(filename, bytes)].
        A timeout cancels the job, so it stops billing."""
        j = self._call("POST", "/api/v2/jobs", {"workflow": workflow},
                       {"Idempotency-Key": uuid.uuid4().hex})   # a retried POST runs once
        jid = j["id"]
        deadline = time.time() + wait_min * 60
        while j.get("status") not in DONE:
            if time.time() > deadline:
                try:
                    self._call("POST", "/api/v2/jobs/%s/cancel" % jid, {}, tries=2)
                finally:
                    raise TimeoutError("Comfy Cloud job %s not done in %s min; cancel sent" % (jid, wait_min))
            self._sleep(self.poll)
            j = self._call("GET", "/api/v2/jobs/" + jid)
        if j["status"] != "succeeded":
            err = j.get("error") or {}
            raise RuntimeError("Comfy Cloud job %s %s: %s %s" % (
                jid, j["status"], err.get("code") or "", self._scrub(err.get("message") or "")[:400]))
        outs, seen = [], set()
        for i, o in enumerate(j.get("outputs") or []):
            if not o.get("url"):
                continue
            name = os.path.basename(o.get("name") or "") or "%s_%d" % (o.get("node_id") or "out", i)
            if name in seen:
                name = "%d_%s" % (i, name)
            seen.add(name)
            outs.append((name, self._call("GET", o["url"], raw=True, timeout=600)))
        return outs


def connect(target="http://127.0.0.1:8188"):
    """"cloud" (or a cloud.comfy.org URL) -> CloudComfy; anything else -> a ComfyUI URL."""
    if target == "cloud" or urllib.parse.urlsplit(target).netloc == urllib.parse.urlsplit(CLOUD).netloc:
        return CloudComfy()
    return Comfy(target)


def mean_luma(path_or_bytes):
    """Mean luminance 0-255 — the objective check that a value-ref pulse actually rendered."""
    import io as _io
    from PIL import Image
    import numpy as np
    src = _io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
    return float(np.asarray(Image.open(src).convert("L"), dtype="float32").mean())
