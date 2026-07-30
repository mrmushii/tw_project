# github-notify — reference

Background for debugging `check.py`. **Not a procedure to follow by hand.** The
skill runs the script; anything reimplemented from this file will skip the state
comparison and misreport.

## State file

`<state-dir>/github-notify-seen.json`, where the state dir is
`$OPENCLAW_STATE_DIR` when set (containers) and `~/.openclaw` otherwise. Note the
variable is **empty in the local exec environment**, which is why the script has
an explicit fallback rather than trusting it.

```json
{
  "last_commit_sha": "",
  "seen_pr_numbers": [],
  "seen_review_ids": [],
  "last_failed_run_id": 0
}
```

A blank `last_commit_sha` means no real baseline has ever been recorded, and the
script treats the run as a first run. The state is written *before* the report is
printed, so a formatting failure cannot cause the same activity to be announced
twice.

## Endpoints

All with `Accept: application/vnd.github+json` and
`Authorization: Bearer $GITHUB_TOKEN`, against
`https://api.github.com/repos/$GITHUB_REPO`:

1. **Commits** — `GET /commits?per_page=20`. Everything above `last_commit_sha`
   is new. If that SHA is absent from the window (force-push, or a long gap), the
   script falls back to reporting the single newest commit rather than replaying
   twenty.
2. **Pull requests** — `GET /pulls?state=open&per_page=20`. New when the number
   is not in `seen_pr_numbers`.
3. **Reviews** — `GET /pulls/<number>/reviews` per open PR. New when the review
   id is not in `seen_review_ids`. Reports `APPROVED` / `CHANGES_REQUESTED` /
   `COMMENTED`.
4. **Failed CI** — `GET /actions/runs?status=completed&per_page=10`. Reported
   when `conclusion == "failure"` and the id exceeds `last_failed_run_id`.
   Includes `html_url` so it can be clicked through.

Failures lead the report — a red CI run outranks a new commit.

## Error handling

- **401 / 403** — token invalid or lacking access. Reported and exits; no retry.
- **404** — wrong `GITHUB_REPO`, or the token cannot see it.
- **Network failure** — reported with the underlying reason.

Rate limit is 5000/hour authenticated and 60 unauthenticated, which is a quick
way to confirm the token is actually being read.

## Why the diffing is in code

Asked to do this comparison in prose, a small model fetched correctly, wrote
state correctly, and still reported "no new activity" for a commit it had just
fetched. It also announced "baseline established" on every run for a while,
because the state path was built from the empty `$OPENCLAW_STATE_DIR` and
silently resolved to the filesystem root. Both failures were silent. The
bookkeeping is deterministic, so it belongs in the script; the model is left to
phrase the result.
