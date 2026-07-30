---
name: github-notify
description: Check a GitHub repository for new commits, pull requests, PR reviews, and failed CI runs, and report anything new since the last check. Use when the user asks about GitHub activity, repo status, PR or CI state, or when running a scheduled repository check.
---

# GitHub activity notifications

Polls the GitHub REST API for a watched repository and reports only what is **new
since the last check**, so a scheduled run stays quiet when nothing has happened.

## How to run this check

**Run the script. Do not do the comparison yourself.**

```sh
python "$HOME/.openclaw/workspace/skills/github-notify/check.py"
```

It loads credentials, reads the state file, polls GitHub, works out what is new,
and writes the state back. Your only job is to relay what it prints:

- `NEW_ACTIVITY in <repo>:` followed by grouped items — report them, keeping the
  grouping, leading with failed CI runs. Put it in your own voice, but do not
  drop or reorder items, and do not add any item it did not print.
- `NO_NEW_ACTIVITY ...` — on a scheduled run, stay silent. Only say "nothing
  new" when the user asked directly.
- `FIRST_RUN: ...` — relay the one-line summary as-is.
- `ERROR: ...` — report the error verbatim and stop. Do not retry in a loop.

Never re-derive "what is new" from your own memory of an earlier check, and
never claim there is no new activity when the script printed `NEW_ACTIVITY`.

The reference below documents what the script does and why. Read it if you need
to debug the script, not to reimplement it by hand.

## Configuration

- `GITHUB_TOKEN` — personal access token with read access to the repo
- `GITHUB_REPO` — the repository as `owner/name`

**Load them by sourcing the state-dir dotenv first.** Begin every run with:

```sh
set -a; . "$HOME/.openclaw/.env"; set +a
```

This is required, not optional. The gateway's exec environment strips
secret-shaped variables, so `GITHUB_TOKEN` is **empty** if you rely on the
inherited environment — `GITHUB_REPO` survives, which makes the failure look
like a half-configured setup rather than a stripped variable. Sourcing the file
fixes both at once.

Never hardcode or echo the token. If it is still missing after sourcing, say so
plainly and stop. Do not guess a repository name.

## Tracking what has already been reported

Keep a small JSON file at this **exact literal path** — do not use
`$OPENCLAW_STATE_DIR`, which is empty in the exec environment and would silently
resolve to the filesystem root:

```
$HOME/.openclaw/github-notify-seen.json
```

Contents:

```json
{
  "last_commit_sha": "",
  "seen_pr_numbers": [],
  "seen_review_ids": [],
  "last_failed_run_id": 0
}
```

Follow this order exactly, every run:

1. **Read the state file first**, before any API call. `cat` it and show yourself
   the contents.
2. **If it exists and `last_commit_sha` is non-empty, this is NOT a first run.**
   Compare against it and report what is new. Never announce "baseline
   established" when a baseline already exists — that is the signature of having
   failed to read the file, and it hides real activity.
3. **If it is missing or `last_commit_sha` is empty**, this is a first run:
   record current state and report only a one-line summary ("watching <repo>,
   currently N open PRs"). Do not dump the entire repo history as if it were new.
4. **Write the file back at the end of every run**, with the newest commit SHA
   you saw, even when nothing was new. Write the real values you fetched — never
   write the empty template above back to disk.

**Do not answer from memory.** If you checked this repository earlier in the
conversation, poll the API again anyway; a cached answer will miss everything
that happened since.

On Render's free tier this file is wiped on every restart, so the first run after
a redeploy behaves like a fresh start. That is expected, not a bug.

## What to check

Set `AUTH='Authorization: Bearer '"$GITHUB_TOKEN"` and
`API="https://api.github.com/repos/$GITHUB_REPO"`, then send
`Accept: application/vnd.github+json` on every request.

1. **New commits** — `GET $API/commits?per_page=10`
   Report any commit newer than `last_commit_sha`: short SHA, message first line, author.

2. **New pull requests** — `GET $API/pulls?state=open&per_page=20`
   Report PRs whose `number` is not in `seen_pr_numbers`: number, title, author.

3. **New PR reviews** — for each open PR, `GET $API/pulls/<number>/reviews`
   Report reviews whose `id` is not in `seen_review_ids`: PR number, reviewer,
   and `state` (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`).

4. **Failed CI runs** — `GET $API/actions/runs?status=completed&per_page=10`
   Report runs with `conclusion == "failure"` and `id > last_failed_run_id`:
   workflow name, branch, and `html_url`.

Parse JSON properly (`jq` if available, otherwise a short Python snippet). Do not
regex-match raw API output.

## Reporting

- **Nothing new:** stay silent on a scheduled run. Only confirm "no new activity"
  when the user asked directly.
- **Something new:** one short line per item, grouped under the four headings
  above. Include the `html_url` for failed CI runs so the user can click through.
- Lead with failures. A red CI run matters more than a new commit.

## Failure handling

- **401 / 403** — the token is invalid or lacks `repo` scope. Say which, and do
  not retry in a loop.
- **404** — the repo name is wrong or the token cannot see it. Report the exact
  `GITHUB_REPO` value used so the mistake is obvious.
- **429 or `x-ratelimit-remaining: 0`** — report the reset time and stop. Do not
  hammer the API.

Never print the token, and never include it in a message or error report.
