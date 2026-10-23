#!/usr/bin/env python3
"""Minimal ComfyUI HTTP client — drive a LOCAL or REMOTE ComfyUI identically.

Remote = a rented GPU reached via SSH `-L` tunnel or the RunPod proxy URL; nothing in
here cares which. See the `remote-comfy` skill for renting/pausing the box.

  from comfy_client import Comfy
  c = Comfy("http://127.0.0.1:8189")
  c.wait_ready()
  name = c.upload("scene.jpg")            # -> filename usable by LoadImage
  imgs = c.run(workflow_dict)             # -> [(filename, bytes), ...]

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


def mean_luma(path_or_bytes):
    """Mean luminance 0-255 — the objective check that a value-ref pulse actually rendered."""
    import io as _io
    from PIL import Image
    import numpy as np
    src = _io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
    return float(np.asarray(Image.open(src).convert("L"), dtype="float32").mean())
