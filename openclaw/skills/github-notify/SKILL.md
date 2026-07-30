---
name: github-notify
description: Check a GitHub repository for new commits, pull requests, PR reviews, and failed CI runs, and report anything new since the last check. Use when the user asks about GitHub activity, repo status, PR or CI state, or when running a scheduled repository check.
---

# GitHub activity notifications

## Run exactly this, and nothing else

```sh
python skills/github-notify/check.py
```

The path is relative on purpose: your working directory is the agent workspace,
which is `~/.openclaw/workspace` locally and `/app/workspace` in the container.
An absolute `$HOME/...` path works locally and fails in the container.

If that command is not found, fall back to `python3` instead of `python`, and
only then to an absolute path.

That single command is the whole procedure. It loads credentials, reads the
state file, polls GitHub, works out what is new, and writes the state back.

**Do not write your own API calls.** No `curl`, no `Invoke-RestMethod`, no
`$API = ...`. Hand-rolled requests miss the state comparison and report activity
that is not new, or stay silent about activity that is. If the command above
fails, report the failure — do not fall back to calling the API yourself.

**Do not answer from memory.** If you checked earlier in this conversation, run
the command again anyway.

## Reporting what it prints

Your only job is to relay the output:

- **`NEW_ACTIVITY in <repo>:`** followed by grouped items — report them in your
  own voice, keeping the grouping and leading with any failed CI runs. Do not
  drop, reorder, or add items.
- **`NO_NEW_ACTIVITY ...`** — on a scheduled run, stay silent. Only say "nothing
  new" when the user asked directly.
- **`FIRST_RUN: ...`** — relay the one-line summary as-is.
- **`ERROR: ...`** — report it verbatim and stop. Do not retry in a loop, and do
  not try another approach.

Never claim there is no new activity when the script printed `NEW_ACTIVITY`.

## Configuration

Set in the environment, or in the state-dir dotenv (`~/.openclaw/.env` locally,
which is what the script reads because the gateway strips secret-shaped variables
from the exec environment):

- `GITHUB_TOKEN` — personal access token with read access to the repo
- `GITHUB_REPO` — the repository as `owner/name`

Never print the token. If configuration is missing the script says so and exits;
relay that and stop.

## Notes

State lives beside the dotenv as `github-notify-seen.json`. On Render's free tier
it is wiped on every restart, so the first run after a redeploy reports a fresh
baseline. That is expected, not a bug.

`REFERENCE.md` in this directory documents the endpoints and the diffing rules.
It is there to help debug `check.py` — not to be reimplemented by hand.
