#!/usr/bin/env bash
# Continuously pull a pod's OUTPUT directory to the local machine while a batch runs.
#
# WHY THIS EXISTS (2026-07-26, cost ~200-400 rendered frames and ~$22):
# A long batch was run ON a pod writing to pod-local disk, with no copy-back. RunPod
# stopped the pod (account balance), the GPUs were reclaimed, the pod could not restart
# ("not enough free GPUs on the host machine") and EVERY frame was lost. Rented boxes are
# EPHEMERAL. Treat pod storage as scratch: if an artifact is not on the laptop, it does
# not exist.
#
#   bash sync-outputs.sh <host> <port> <remote_dir> <local_dir> [interval_secs]
#
# Copies files (RECURSIVELY, preserving subdirectories) that are missing locally or differ
# in size, via a tar stream (no rsync dependency); loops until killed. Safe to run
# alongside the batch; safe to re-run; never deletes anything.
#
# IT DEDUPLICATES BY PATH + SIZE, NOT BY CONTENT. Cheap, and a trap when a batch is RE-RUN
# at different settings and a regenerated f0000.png happens to keep the same byte size:
# the OLD file stays locally and the final set silently mixes two looks (2026-07-26).
# Before re-running a batch with changed parameters, MOVE the local output dir aside —
# do not rely on this loop to overwrite. Same applies to the harness's own resume check:
# it skips frames already on the POD, so wipe those too, or it will not redo them.
set -u
HOST="${1:?host}"; PORT="${2:?port}"; REMOTE="${3:?remote dir}"; LOCAL="${4:?local dir}"
INTERVAL="${5:-60}"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"
# slug identifies WHICH remote dir this loop covers, for the per-directory sentinel
SLUG="$(echo "$REMOTE" | tr -c "A-Za-z0-9" "_" )"
FAILS=0; FAIL_LIMIT="${SYNC_FAIL_LIMIT:-10}"   # ~10 polls of unreachable host -> exit
mkdir -p "$LOCAL"
echo "sync: $HOST:$REMOTE -> $LOCAL every ${INTERVAL}s (ctrl-c to stop)"
while true; do
  # list remote files RECURSIVELY with sizes ("<bytes> <relpath>"); outputs often live in
  # per-run subdirectories, which a flat `ls` + scp silently skipped (2026-10-20).
  # Assumes no spaces in output paths (ComfyUI/harness names have none).
  REMOTE_LIST=$(ssh $SSHOPT -p "$PORT" root@"$HOST" \
    "cd $REMOTE 2>/dev/null && find . -type f -printf '%s %P\n'" 2>/dev/null)
  RC=$?
  # DIE WHEN THE HOST DIES. A while-true with no liveness check outlives the pod it syncs:
  # 26 of these ran ~21h against a terminated host (ssh exit 255) before anyone noticed
  # (2026-07-27). Distinguish "no new files" (rc 0, empty list) from "cannot reach host"
  # (rc != 0) and give up after FAIL_LIMIT consecutive failures.
  if [ "$RC" -ne 0 ]; then
    FAILS=$((FAILS+1))
    if [ "$FAILS" -ge "$FAIL_LIMIT" ]; then
      echo "sync: host unreachable ${FAILS}x (ssh rc=$RC) — pod is gone, exiting rather than"
      echo "      retrying forever. Local copy: $(ls -1 "$LOCAL" 2>/dev/null | wc -l) files."
      exit 1
    fi
    sleep "$INTERVAL"; continue
  fi
  FAILS=0
  NEW=""
  while read -r size rel; do
    [ -n "$rel" ] || continue
    have=$(stat -c %s "$LOCAL/$rel" 2>/dev/null || echo -1)
    [ "$have" = "$size" ] || NEW="$NEW $rel"
  done <<< "$REMOTE_LIST"
  COPY_OK=1
  if [ -n "$NEW" ]; then
    # one tar stream keeps the directory structure; BOTH ends must succeed
    # shellcheck disable=SC2086
    ssh $SSHOPT -p "$PORT" root@"$HOST" "cd $REMOTE && tar cf - $NEW" | tar xf - -C "$LOCAL"
    ST=("${PIPESTATUS[@]}")   # capture NOW: the next command (even `[`) overwrites PIPESTATUS
    [ "${ST[0]}" = 0 ] && [ "${ST[1]}" = 0 ] || COPY_OK=0
    # A clean exit is not proof: verify every remote file is now present at its remote size.
    while read -r size rel; do
      [ -n "$rel" ] || continue
      [ "$(stat -c %s "$LOCAL/$rel" 2>/dev/null)" = "$size" ] || COPY_OK=0
    done <<< "$REMOTE_LIST"
    if [ "$COPY_OK" = 1 ]; then
      echo "$(date +%H:%M:%S) pulled $(echo $NEW | wc -w) new -> $(find "$LOCAL" -type f | wc -l) local files"
    else
      echo "$(date +%H:%M:%S) SYNC FAILED for some of: $NEW  (sentinel NOT touched)"
    fi
  fi
  # Tell the on-pod watchdog that THIS DIRECTORY is safely on the laptop - but ONLY when
  # every remote file is verified local. A flat loop once claimed this for GLBs that never
  # left the pod (2026-10-20). PER-DIRECTORY, not global: a single /workspace/.synced said
  # "everything is safe" the moment ANY loop touched it (2026-07-27).
  if [ "$COPY_OK" = 1 ]; then
    ssh $SSHOPT -p "$PORT" root@"$HOST"     "mkdir -p /workspace/.synced.d && touch /workspace/.synced.d/$SLUG && touch /workspace/.synced"     >/dev/null 2>&1
  fi
  sleep "$INTERVAL"
done
