# /workspace/.busy is a heartbeat, not a flag

**Context.** `autostop.py` originally refused to stop while `/workspace/.busy` existed.
A sweep script touched it at the top and exited without removing it; the watchdog held
a fully idle H100 for ~3 hours (~$9). A lock that outlives its job looks exactly like
one nobody cleaned up.

**Decision.** The lock counts only while **fresh** (`--lock-ttl-min`, default 20). Long
jobs refresh it with `pod/hold-busy.sh -- <cmd>` (or `--pid`), which traps
EXIT/INT/TERM to release it. A SIGKILLed holder simply lets it go stale.

**Consequence found later (2026-10-23).** `launch-sharded.sh` still touched the lock
once. Because the watchdog polls only GPU0's queue, a batch that ran past the TTL after
shard 0 drained was unprotected. The launcher's wait loop now refreshes the lock, and a
tripwire asserts it.

**Would change it.** Making autostop poll every per-GPU port (8188+N) would remove the
launcher's need to hold the lock at all. Not yet done; see `docs/open-questions.md`.
