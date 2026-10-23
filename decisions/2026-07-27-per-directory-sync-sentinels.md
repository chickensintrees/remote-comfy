# Sync sentinels are per directory

**Context.** Before terminating a pod (rather than stranding it on a low-stock GPU),
`autostop.py` checks that outputs reached the laptop. That check read one global
`/workspace/.synced`, so *any* running sync loop vouched for *all* outputs. It could have
destroyed a pod still holding unsynced frames from a different directory.

**Decision.** `local/sync-outputs.sh` writes `/workspace/.synced.d/<slug>` for the one
remote directory it covers, and only after re-verifying every file locally. Run autostop
with `--outputs-root`: every directory with recent output then needs its own sentinel,
and a sentinel older than the newest file re-flags the directory. Without
`--outputs-root` the check logs `[WEAK]`.

**Also learned.** A sync loop with no liveness check outlived its host: 26 loops retried
a terminated pod for ~21h. The loop now exits non-zero after `SYNC_FAIL_LIMIT`
consecutive ssh failures.

**Would change it.** Content hashing instead of path+size (see the dedupe caveat at the
top of `sync-outputs.sh`).
