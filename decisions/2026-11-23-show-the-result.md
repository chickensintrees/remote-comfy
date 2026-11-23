# Show the result in the session

**Context.** The point of the toolkit is that you ask Claude Code for an asset and get it
back without running ComfyUI or a GPU yourself. Until now the harness stopped when the
files reached disk: nothing told the agent to look at them or show them, and Claude Code
has no built-in media viewer, so the person had to go and find the files.

**Decision.** Showing the result is a step of every job (skill "Show the result", AGENTS.md
rule 9, playbook section 8):

1. The agent looks at every output first with its file-reading tool, which shows it images,
   and fixes or re-runs anything broken before showing it.
2. It sends the files themselves to the person through the app's file tool (SendUserFile
   in the Claude desktop and web apps), several in one call. For a big batch it sends the
   best handful and offers `remote_comfy/gallery.py`'s page to open in the browser.
3. In a plain terminal, where no file tool exists, it gives the paths and offers to open
   the gallery.

**Why the files, not a page.** Checked in the desktop app on 2026-11-23: a sent PNG shows as
a picture in the transcript; a sent gallery page shows as a blank HTML card, both the one
that links its files and one with the files inside it as data URIs (22.5 MB). So the page
is for the browser only, and its `--embed` option was removed the same day.

**Checked on 2026-11-23.** The gallery page, built from six real outputs of the 2026-11-15
run, loads every image and plays the 5-second clip in Chromium from a local server.

**Tried and set aside.** Sending a gallery page through the app (above). A contact sheet
image (needs PIL, and cannot play video). `<model-viewer>` for 3D (needs a script from a
CDN, and the GLB fetch fails from `file://`).

**What would change it.** An app that renders a sent HTML page inline would make the
gallery the one thing to send.
