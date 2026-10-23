#!/usr/bin/env bash
# Install the remote-comfy Claude Code skill at USER level so it loads in every project.
# A skill stored under <repo>/.claude/skills is directory-scoped and stays invisible from
# other projects (see decisions/2026-07-25-user-level-skill.md).
#
#   bash scripts/install-skill.sh            # copies skills/remote-comfy -> ~/.claude/skills/
#
# The skill finds the tools via REMOTE_COMFY_HOME; this prints the line to add.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/remote-comfy"
mkdir -p "$DEST"
cp "$ROOT/skills/remote-comfy/SKILL.md" "$DEST/SKILL.md"
echo "installed: $DEST/SKILL.md"
echo "add to your shell profile:  export REMOTE_COMFY_HOME=\"$ROOT\""
