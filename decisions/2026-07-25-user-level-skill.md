# The skill installs at user level, the source lives in this repo

**Context.** The toolkit first lived at `<project>/.claude/skills/remote-comfy`. Claude
Code discovers a repo-scoped skill only once a file-level tool touches that subtree, so
the skill was invisible from every *other* project, which were exactly the situations
its description advertised.

**Decision.** This repo is the canonical source. `scripts/install-skill.sh` copies
`skills/remote-comfy/SKILL.md` to `~/.claude/skills/remote-comfy/`, and the skill finds
the tools through `REMOTE_COMFY_HOME`. Only the thin skill file is deployed, so there is
one copy of the tools to keep current.

**Rejected.** Copying the whole toolkit into `~/.claude/skills` (the original
arrangement). It worked, but produced three drifting copies within three months.

**Would change it.** Claude Code gaining a supported way to install a skill that
references a repo path, or a plugin packaging this repo directly.
