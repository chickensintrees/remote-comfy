# remote-comfy: setup

This file is for Claude Code. A person pasted a line asking you to set up
remote-comfy with them. Setup rents nothing and spends nothing. Do not create,
start or stop a pod during setup, even to test it; offer that as a separate
step at the end, and only on the person's explicit yes.

1. Tell the person what will happen: you will clone one public repository,
   run its offline checks, install its Claude Code skill, and walk them through
   storing their RunPod API key. You will ask before changing anything outside
   the cloned folder.
2. Check that `git --version`, `ssh -V` and `bash --version` work, and find a
   working Python 3.9 or newer by running it (`python3 -c "print(1)"`, then
   `python -c "print(1)"`; on Windows `python3` can be a Microsoft Store stub
   that exits 49). On Windows, bash comes with Git for Windows. If something is
   missing, say what and where to get it, and wait.
3. Clone the repository into the person's home folder, unless they name another
   place. Use the real absolute path of that folder for `<HOME>`. If the folder
   already exists, do not delete or overwrite it: ask whether to use it as is.

       git clone https://github.com/chickensintrees/remote-comfy.git "<HOME>/remote-comfy"

4. Run the offline checks from the clone. They need no network, GPU or key.
   The last line must be `ALL PASS`; if it is not, stop and show the person the
   failures.

       python tests/test_runpod_ops.py

5. Read `AGENTS.md` in the clone with your file-reading tool, then follow its
   rules for the rest of this setup and every session after it.
6. Ask before installing the skill, because it writes to `~/.claude/skills`.
   Then run `bash scripts/install-skill.sh`, and ask before adding the
   `REMOTE_COMFY_HOME` line it prints to the person's shell profile.
7. The API key. Never ask for the key in the chat, never echo or log it, and
   never write it to a file. The person creates a key in the RunPod console
   (Settings, API Keys) and stores it in one of two ways,
   typing it into their own terminal:
   - in the OS keyring (ask before running `pip install keyring`):
     `python -m keyring set remote-comfy runpod`
   - or as the environment variable `RUNPOD_API_KEY` in their shell profile.
   Then check it with a read-only call:

       python remote_comfy/pod_ctl.py balance

8. SSH key. RunPod puts SSH keys into a pod when it boots, so the person's
   public key must be in RunPod (Settings, SSH Public Keys) before their first
   pod. Show them their public key file if they have one; if they do not, offer
   to create one with `ssh-keygen` and ask first.
9. Finish by pointing them at `docs/playbook.md` for the first run, and say that
   it rents real hardware: the watchdog `autostop.py` goes on every pod.

Source: https://github.com/chickensintrees/remote-comfy
Project page: https://billmoore.ai/remote-comfy/
