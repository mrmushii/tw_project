# Handover — OpenClaw local setup (blocked on device scopes) — 2026-07-30

## Goal

University project with two graded deliverables:

1. **Comparison study** — classify an image dataset with a Claude vision agent vs a
   fine-tuned VGG-16 on an identical test set, analyse which worked better and why.
   **This is COMPLETE.**
2. **OpenClaw deployment** — a self-hosted OpenClaw agent on Haiku with three added
   features (reminders, morning briefing, GitHub notifications), hosted on Render and
   demoed live in a lab exam. **This is PARTLY DONE and currently blocked.**

Everything must run on **Haiku** (`claude-haiku-4-5` / `anthropic/claude-haiku-4-5`) —
user requirement, non-negotiable. Auth is a **Claude Pro subscription token**, not a
funded API key (the key in `.env` history was real but had zero credit).

## State: what is DONE

### Deliverable 1 — comparison study (complete, verified)

- Dataset: Intel Image Classification, 6 classes, 864 train / 216 test, balanced.
  Verified by `scripts/check_split.py`: no train/test filename overlap, all readable.
- **Agent branch:** 216/216 classified via `scripts/02_agent_classify.py`.
  **0.917 accuracy**, macro-F1 0.916. Zero blank predictions, zero malformed responses.
- **VGG-16 branch:** trained on Kaggle GPU, `results/vgg16_predictions.csv` downloaded.
  **0.903 accuracy**, macro-F1 0.903.
- **Comparison:** `scripts/03_compare_results.py` re-run at wrap-up, reproduces
  identical figures. Artifacts in `results/`: `comparison_report.md`,
  `confusion_matrices.png`, both prediction CSVs.
- **Key analytical result** (already written up): the gap is **not significant**
  (McNemar exact, p = 0.690) — the branches are statistically tied. The real finding is
  that error *structures* differ: the agent fails one-directionally
  (glacier→mountain 6, reverse 0 — a semantic category judgement), VGG-16 fails
  symmetrically (5 each way — perceptual non-discrimination). Only 7/216 defeat both;
  oracle ensemble bound 96.8%.
- **Report/slides source:** `docs/PROJECT_REPORT.md` (657 lines) — Part A method,
  Part B analysis, Part C 14-slide outline, Part D OpenClaw, Part E remaining work.

### Deliverable 2 — OpenClaw (partial)

- Installed: OpenClaw **2026.5.12** (`npm i -g openclaw`), Node 22.16.0.
- `openclaw onboard --non-interactive --accept-risk --mode local` succeeded — config,
  workspace, and session dirs created.
- Config verified: `gateway.mode local`, `bind loopback`, token auth,
  `session.dmScope per-channel-peer`, model `anthropic/claude-haiku-4-5`.
- Auth profile `anthropic:default [anthropic/token]` created by the user running
  `openclaw models auth setup-token --provider anthropic --yes` in a real terminal.
  `openclaw models list` shows `Auth: yes`.
- **End-to-end agent turn on Haiku works:**
  `openclaw agent --agent main -m "Reply with exactly the word: OK"` → `OK`.
- Cron scheduler reports `enabled: true`, store `~/.openclaw/cron/jobs.json`, 0 jobs.
- Deployment artifacts written and committed (all validated, no secrets):
  `openclaw/openclaw.json`, `openclaw/Dockerfile`, `render.yaml`,
  `openclaw/skills/github-notify/SKILL.md`.

## State: what is IN PROGRESS / NOT started

### ~~THE BLOCKER — device scope deadlock~~ — RESOLVED 2026-07-30 18:01

Fixed by **offline file surgery**, not the pairing handshake. `devices/paired.json` had
`approvedScopes: ["operator.write"]` while `devices/pending.json` held one stable
`isRepair: true` request from the *same* device asking for `operator.admin` +
`operator.pairing`. The id churn was only in the CLI's live connection — the store was
stable all along. Fix: stop the gateway, add all four scopes to the paired entry's
`scopes`, `approvedScopes` **and** `tokens.operator.scopes` (all three must agree),
replace `pending.json` with `{}`, restart. The gateway accepts the hand-edited entry —
**there is no signature or checksum on that table.** Backups left at
`devices/paired.json.bak-scopefix` and `pending.json.bak-scopefix`.

Note: Claude Code's permission classifier blocks both Bash and Edit writes to
`~/.openclaw/devices/*.json` (local credential store). **The user must make this edit by
hand** — don't burn turns looking for a tool that will do it.

Scheduling then verified: `openclaw cron add ... --at 2m` succeeded (the command that
used to throw `gateway closed (1008)`), and `openclaw cron runs --id <job-id>` returned
`status: ok`, `summary: "SCHEDULED_OK"`, `model: claude-haiku-4-5`, duration 22.9s.
`cron runs` **requires `--id`**; `cron delete` does **not** take `--id`. One-off jobs
clear themselves from `cron list` after firing even with `--keep-after-run`.

WSL2 and `openclaw reset` are no longer needed. Original diagnosis kept below for context.

### The original blocker writeup (historical)

`openclaw cron add` fails with:

```
gateway closed (1008): pairing required: device is asking for more scopes
than currently approved
```

The CLI device is paired with `operator.read` + `operator.write`, but privileged
commands need `operator.admin` + `operator.pairing`. **Every CLI connection attempt
mints a new pending request id**, so by the time `openclaw devices approve <id>` runs,
that id is stale → `unknown requestId`. Already tried and failed, do not repeat:

- `devices approve <id>` with a freshly-read id — id churns, fails
- `devices approve --latest` — only *displays* the request, does not approve
- `devices approve --token <gateway token>` — device scope is the gate, not gateway auth
- `devices clear --yes --pending` — itself blocked by the same deadlock

**`openclaw doctor --fix` was proposed but the user declined it.** Do not run it
without asking again — it also auto-disables unusable skills as a side effect, which is
a broader change than the pairing repair alone.

Untried options, roughly in order of safety:

1. Run `openclaw devices approve <id>` **in a real terminal** while the gateway runs in
   another window — an interactive TTY may complete the handshake the piped CLI cannot.
2. Kill the gateway (see below), then inspect `~/.openclaw/identity/` for the device
   pairing table and remove the stale limited-scope entry so the next connect re-pairs
   cleanly. Back up the file first.
3. `openclaw reset` — resets local config/state, keeps the CLI. **Destructive**: would
   discard the working auth profile, requiring the user to re-run `setup-token`. Last resort.
4. Consider WSL2 — install printed *"Windows detected — OpenClaw runs great on WSL2!
   Native Windows might be trickier."* This deadlock may be a native-Windows issue.

**A gateway process is still listening on `127.0.0.1:18789` (PID 5432 at wrap-up).**
`TaskStop` does not kill it — only the shell wrapper. Find and kill it via
`netstat -ano | grep 18789`.

### Remaining steps, in order

1. ~~**Resolve the device scope deadlock.**~~ DONE — see resolved section above.
2. ~~**Verify scheduling.**~~ DONE — `SCHEDULED_OK` on Haiku, 2026-07-30 18:05.
3. **Telegram** ← **NEXT. Blocked on the user creating the bot.** — user must create a bot via @BotFather (`/newbot`) and put the token in
   `.env` as `TELEGRAM_BOT_TOKEN=...`. Not yet set. Then enable the channel, run
   `openclaw gateway`, `openclaw pairing list telegram`,
   `openclaw pairing approve telegram <CODE>`. Long polling is the default — no
   inbound webhook needed, which is what makes Render free tier viable.
4. **Set the command owner** — doctor flagged this:
   `openclaw config set commands.ownerAllowFrom '["telegram:<your-user-id>"]'`.
   Needs the Telegram user id (`openclaw directory` can look it up).
5. **Feature 1 — reminders.** Native scheduling + memory, no code. Prove first: it
   validates the stack the briefing also depends on.
6. **Feature 2 — morning briefing.** One scheduled natural-language instruction;
   weather needs a web-search call in the scheduled prompt.
7. **Feature 3 — GitHub notifications.** `openclaw/skills/github-notify/SKILL.md` is
   written but untested. Needs `GITHUB_TOKEN` (repo scope) + `GITHUB_REPO` in env.
   **Note:** OpenClaw ships bundled `github` and `gh-issues` skills that need the
   GitHub CLI — possibly less work than the custom skill locally, though the custom
   one is better for the Render container (curl + PAT, no `gh` binary).
8. **Push, then deploy to Render** via Blueprint; set the four `sync:false` env vars.
9. **Keep-alive cron** — external pinger (cron-job.org) hitting
   `https://<service>.onrender.com/v1/models` every 10 min (free services sleep at ~15).
10. **Rehearse a local fallback** for the lab exam — Render free tier failing mid-demo
    is realistic.

### Optional, would strengthen the study

- Inspect the 7 both-wrong images by eye to test the label-noise hypothesis
  (4 are `glacier`): `glacier_2113`, `glacier_4210`, `glacier_7721`, `glacier_8927`,
  `buildings_7084`, `sea_17759`, `sea_6432`. Currently a conjecture in the report; a
  look would make it a finding.
- Repeated agent runs to quantify non-determinism (currently a stated limitation).
- Prompt ablation defining the buildings/street and glacier/mountain boundaries — would
  test whether the semantic errors are correctable by prompt.

## Key decisions & gotchas

- **Do not claim the agent "won."** p = 0.690. The report deliberately frames it as
  statistical parity at zero labelling cost. This was corrected mid-session after an
  earlier overclaim — don't reintroduce it.
- **Do not re-run `scripts/01_prepare_dataset.py`.** It wipes and rebuilds both splits,
  which would orphan all 432 collected predictions.
- **Do not loosen the alignment checks in `03_compare_results.py`.** They are the
  guarantee that makes the comparison valid. If one fires, something is genuinely wrong.
- **Never pass `--set-default` to an OpenClaw auth command** — it applies
  `claude-opus-4-7` and violates the Haiku requirement.
- **`tools.profile` is intentionally `coding`, not the docs' hardened `messaging`.**
  Applying their `exec: deny` / `group:fs` denies would break the features. The
  security trade-off is documented in CLAUDE.md and in the report rather than hidden.
- **Prefix OpenClaw commands** with
  `export PATH="$PATH:/c/Users/mushf/AppData/Roaming/npm"`.
- `.env` holds `ANTHROPIC_AUTH_TOKEN` and is gitignored. Never commit or echo it.
- **Consider committing the results evidence.** `.gitignore` excludes `results/*.csv`
  and `results/*.png`, so both prediction CSVs and the confusion-matrix figure are NOT
  in the repo — only the generated `comparison_report.md`. ~120 KB total, and it is the
  raw data behind every number in the report. User was asked, has not decided.

## Files touched

Committed and pushed (`085b1da` on `main`, remote `github.com/mrmushii/tw_project`):

- `scripts/02_agent_classify.py` — auth reworked (`load_credentials()`, `build_client()`)
- `.env.example` — documents both auth paths
- `.gitignore` — ignore `data/splits.zip`
- `CLAUDE.md` — new
- `docs/PROJECT_REPORT.md` — new
- `openclaw/openclaw.json`, `openclaw/Dockerfile`, `openclaw/skills/github-notify/SKILL.md` — new
- `render.yaml` — new
- `results/comparison_report.md` — new

Uncommitted at handover: `CLAUDE.md` (OpenClaw gotchas + security posture sections
added during wrap-up) and this `HANDOVER.md`.

Untracked-but-present (gitignored): `.env`, `data/splits.zip` (16 MB, for Kaggle),
`results/agent_predictions.csv`, `results/vgg16_predictions.csv`,
`results/confusion_matrices.png`.

Outside the repo: `~/.openclaw/` (config, workspace, auth profile, cron store).
