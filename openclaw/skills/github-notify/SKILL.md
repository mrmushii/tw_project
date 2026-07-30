---
name: github-notify
description: Check a GitHub repository for new commits, pull requests, PR reviews, and failed CI runs, and report anything new since the last check. Use when the user asks about GitHub activity, repo status, PR or CI state, or when running a scheduled repository check.
---

# GitHub activity notifications

Polls the GitHub REST API for a watched repository and reports only what is **new
since the last check**, so a scheduled run stays quiet when nothing has happened.

## Configuration

Both come from the environment — never hardcode or echo them:

- `GITHUB_TOKEN` — personal access token with `repo` scope
- `GITHUB_REPO` — the repository as `owner/name`

If either is unset, say so plainly and stop. Do not guess a repository name.

## Tracking what has already been reported

Keep a small JSON file at `$OPENCLAW_STATE_DIR/github-notify-seen.json`:

```json
{
  "last_commit_sha": "",
  "seen_pr_numbers": [],
  "seen_review_ids": [],
  "last_failed_run_id": 0
}
```

Read it before polling and write it back after. **On the first ever run the file
will not exist** — in that case, record current state and report only a one-line
summary ("watching <repo>, currently N open PRs"). Do not dump the entire repo
history as if it were all new.

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
