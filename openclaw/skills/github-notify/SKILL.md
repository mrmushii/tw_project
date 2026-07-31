---
name: github-notify
description: Check a GitHub repository for commits, pull requests, PR reviews, and failed CI runs. Use for ANY question about the watched repository - new activity, repo status, the latest or last commit and its message, who pushed what, open PRs, review state, or CI failures - and for scheduled repository checks. Never clone the repo or read git history to answer these; this skill queries the GitHub API directly.
---

# GitHub activity notifications

## Run exactly this, and nothing else

```sh
sh -c 'C=/app/workspace/skills/github-notify/check.py; [ -f "$C" ] || C=$HOME/.openclaw/workspace/skills/github-notify/check.py; python "$C"'
```

Copy that line verbatim; it works in the container and on the local install.

**Do not simplify it to a bare relative path** like
`python skills/github-notify/check.py` — that only works if your working
directory happens to be the workspace, and on the scheduled path it is not, so
the run fails with "file not found" and you report a broken check. **Do not
substitute a single hardcoded absolute path either** — the two candidates above
differ per environment and the line picks whichever exists.

If the command succeeded, you are done — do not run a second variant to
double-check. If `python` is genuinely missing, use `python3` in the same line.

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

## Questions about specific commits

For "what was the last commit message?", "who pushed last?", "show me recent
commits" — use the `commits` subcommand. It is read-only and does not disturb the
activity state:

```sh
sh -c 'C=/app/workspace/skills/github-notify/check.py; [ -f "$C" ] || C=$HOME/.openclaw/workspace/skills/github-notify/check.py; python "$C" commits -n 5'
```

It prints `COMMITS in <repo> (newest first):` and one line per commit with short
SHA, subject, author and date. Relay what you need from that.

**Never hand-roll the request** — no `curl`, no `Invoke-RestMethod`. `$GITHUB_TOKEN`
is **empty** in your shell: the gateway strips secret-shaped variables from the
exec environment. A curl using it fails on auth, and reporting "the GitHub token
isn't configured" on that basis is wrong — the token is configured, it just only
reaches `check.py`, which reads it from the dotenv itself.

**Never clone the repository or read local git history** — the workspace is not a
checkout of it, and cloning to answer a one-line question is the wrong shape of
answer.

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
