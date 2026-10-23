# Publishing as a standalone harness repo

**Context.** The toolkit grew inside a personal skills folder and was mirrored into an
agent-coordination repo; the copies had already drifted (provision 139 vs 171 lines).

**Decision.** One public repo, laid out by *where code runs* (`remote_comfy/` laptop,
`pod/` on the pod, `local/` laptop→pod), with the playbook split out of the skill into
`docs/`. Tests address tools through a single path map and assert doc lessons against
`AGENTS.md` + skill + `docs/` together, so prose can move between files but not vanish.

**Fixed while extracting.** `launch-sharded.sh` used `curl` (absent on the pod image) for
queue-clear and readiness, and touched the heartbeat lock only once. Both are now
tripwired. Neither fix has yet been exercised on a live pod.

**Removed.** Personal keyring service names, pod and volume IDs, private project paths,
and per-session attributions. The key now resolves `RUNPOD_API_KEY` → OS keyring
(`remote-comfy`/`runpod`, overridable).
