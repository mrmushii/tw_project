#!/usr/bin/env python3
"""Deterministic GitHub activity check for the github-notify skill.

The comparison between "what the API returns now" and "what we saw last time"
is pure bookkeeping, so it lives here rather than in the model's head. A small
model asked to do this in prose will fetch correctly, update state correctly,
and still report "no new activity" for a commit it just saw. Encoding it here
removes that failure mode entirely: the skill only has to relay this output.

Reads credentials from ~/.openclaw/.env because the gateway strips
secret-shaped variables from the agent's exec environment.

Exit codes: 0 = ran fine (new activity or not), 1 = configuration/API problem.
"""

import json
import os
import sys
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
ENV_PATH = os.path.join(HOME, ".openclaw", ".env")
STATE_PATH = os.path.join(HOME, ".openclaw", "github-notify-seen.json")
API = "https://api.github.com"

EMPTY_STATE = {
    "last_commit_sha": "",
    "seen_pr_numbers": [],
    "seen_review_ids": [],
    "last_failed_run_id": 0,
}


def load_env():
    """Parse the state-dir dotenv. Never print the values."""
    env = {}
    try:
        with open(ENV_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        sys.exit(f"ERROR: {ENV_PATH} not found. Cannot authenticate.")
    return env


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            state = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(EMPTY_STATE), True
    merged = dict(EMPTY_STATE)
    merged.update(state)
    # A blank sha means we have never recorded a real baseline.
    return merged, not merged["last_commit_sha"]


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def get(path, token):
    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "openclaw-github-notify",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            sys.exit(f"ERROR: GitHub returned {exc.code} — token invalid or lacks access.")
        if exc.code == 404:
            sys.exit(f"ERROR: 404 for {path} — check GITHUB_REPO.")
        sys.exit(f"ERROR: GitHub returned {exc.code} for {path}.")
    except urllib.error.URLError as exc:
        sys.exit(f"ERROR: could not reach GitHub ({exc.reason}).")


def main():
    env = load_env()
    token = env.get("GITHUB_TOKEN", "")
    repo = env.get("GITHUB_REPO", "")
    if not token:
        sys.exit("ERROR: GITHUB_TOKEN missing from ~/.openclaw/.env")
    if not repo:
        sys.exit("ERROR: GITHUB_REPO missing from ~/.openclaw/.env")

    state, first_run = load_state()
    base = f"/repos/{repo}"

    commits = get(f"{base}/commits?per_page=20", token)
    pulls = get(f"{base}/pulls?state=open&per_page=20", token)
    runs = get(f"{base}/actions/runs?status=completed&per_page=10", token).get(
        "workflow_runs", []
    )

    newest_sha = commits[0]["sha"] if commits else state["last_commit_sha"]

    # Commits above the last-seen SHA are new. If the SHA is absent from the
    # window (force-push, or a long gap), fall back to the single newest.
    new_commits = []
    if not first_run:
        shas = [c["sha"] for c in commits]
        if state["last_commit_sha"] in shas:
            new_commits = commits[: shas.index(state["last_commit_sha"])]
        elif commits and commits[0]["sha"] != state["last_commit_sha"]:
            new_commits = commits[:1]

    new_pulls = [p for p in pulls if p["number"] not in state["seen_pr_numbers"]]

    new_reviews = []
    for pr in pulls:
        for review in get(f"{base}/pulls/{pr['number']}/reviews", token):
            if review["id"] not in state["seen_review_ids"]:
                new_reviews.append((pr["number"], review))

    failed = [
        r
        for r in runs
        if r.get("conclusion") == "failure" and r["id"] > state["last_failed_run_id"]
    ]

    # Persist before reporting, so a formatting problem cannot cause a repeat.
    save_state(
        {
            "last_commit_sha": newest_sha,
            "seen_pr_numbers": sorted({p["number"] for p in pulls}
                                      | set(state["seen_pr_numbers"])),
            "seen_review_ids": sorted(set(state["seen_review_ids"])
                                      | {r["id"] for _, r in new_reviews}),
            "last_failed_run_id": max(
                [state["last_failed_run_id"]] + [r["id"] for r in failed]
            ),
        }
    )

    if first_run:
        print(f"FIRST_RUN: watching {repo}, currently {len(pulls)} open PRs. "
              f"Baseline recorded at {newest_sha[:7]}.")
        return

    lines = []
    if failed:  # failures lead — a red CI run outranks a new commit
        lines.append("Failed CI runs:")
        for r in failed:
            lines.append(f"  - {r['name']} on {r['head_branch']}: {r['html_url']}")
    if new_reviews:
        lines.append("New PR reviews:")
        for number, r in new_reviews:
            lines.append(f"  - PR #{number}: {r['user']['login']} -> {r['state']}")
    if new_pulls:
        lines.append("New pull requests:")
        for p in new_pulls:
            lines.append(f"  - #{p['number']} {p['title']} (by {p['user']['login']})")
    if new_commits:
        lines.append("New commits:")
        for c in new_commits:
            msg = c["commit"]["message"].splitlines()[0]
            author = c["commit"]["author"]["name"]
            lines.append(f"  - {c['sha'][:7]} {msg} ({author})")

    if lines:
        print(f"NEW_ACTIVITY in {repo}:")
        print("\n".join(lines))
    else:
        print(f"NO_NEW_ACTIVITY in {repo} (baseline {newest_sha[:7]}).")


if __name__ == "__main__":
    main()
