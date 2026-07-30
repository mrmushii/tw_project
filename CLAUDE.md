# CLAUDE.md

University project. Two deliverables that share this repo:

1. **Comparison study** — classify an image dataset with a Claude vision agent vs a fine-tuned VGG-16, on an identical test set, then analyse which won and why.
2. **OpenClaw deployment** — a self-hosted OpenClaw agent with added functionality (scheduled briefing, reminders, GitHub notifications), hosted on Render, demoed live in a lab exam.

Graded on a project report + presentation. Optimise for *defensible analysis and a working demo*, not production robustness.

---

## Dataset (already prepared — do not regenerate without reason)

Intel Image Classification (Kaggle `puneet6060/intel-image-classification`), 6 classes:
`buildings, forest, glacier, mountain, sea, street`

| Split | Per class | Total |
|---|---|---|
| `data/splits/train/` | 144 | 864 |
| `data/splits/test/` | 36 | 216 |

Built by `scripts/01_prepare_dataset.py` (seed 42, 180/class sampled, 80/20). **Re-running deletes and rebuilds both splits** — any predictions already collected become unalignable. Don't re-run unless you also discard `results/*_predictions.csv`.

Filenames are class-prefixed (`forest_123.jpg`) so the basename is a globally unique key. This is what lets the agent CSV (absolute Windows paths) align with the VGG-16 CSV (`test/<class>/<file>` from Kaggle). **Preserve this convention.**

## The invariant that makes the project valid

Both branches are scored **only** on `data/splits/test/`, the same 216 images. VGG-16 trains on `train/`; the agent never sees `train/` at all (it is zero-shot). `03_compare_results.py` exits fatally if the two CSVs disagree on which images they cover or on any true label. **Never "fix" that check by loosening it** — if it fires, the split or a prediction run is genuinely broken.

## Pipeline

| Step | Script | Runs on | Output |
|---|---|---|---|
| 2 | `scripts/01_prepare_dataset.py` | Local | `data/splits/` |
| — | `scripts/check_split.py` | Local | balance / leakage check |
| 3 | `scripts/02_agent_classify.py` | Local | `results/agent_predictions.csv` |
| 4 | `kaggle/vgg16_train.ipynb` | **Kaggle GPU** | `results/vgg16_predictions.csv` (download manually) |
| 5 | `scripts/03_compare_results.py` | Local | `comparison_report.md`, `confusion_matrices.png` |
| 6 | `scripts/04_presentation_figures.py` | Local | `results/figures/*.png` (+ `--dark` variants) |

`04_presentation_figures.py` is read-only and re-derives its own alignment, so it
cannot disagree with step 5. Seven figures for the report/slides — index and
per-figure purpose in `results/figures/README.md`. Two series only: blue = agent,
orange = VGG-16, a colourblind-safe pair; keep that mapping fixed across figures.

TensorFlow is deliberately **not** in `requirements.txt` — VGG-16 trains on Kaggle's free GPU, not locally. Don't add it.

`02_agent_classify.py` is resumable and crash-safe: it flushes each row immediately and skips filepaths already in the CSV. Always smoke-test with `--limit 10` before a full run. To re-run from scratch, delete the CSV.

Model for classification: `claude-haiku-4-5` (cheapest, adequate for one-word output). Do not silently upgrade this — the model choice is a documented variable in the report.

## Credentials

`.env` is gitignored. Never commit it, never paste key values into chat, code, or the report.

**Active path: Claude Pro subscription token.** Verified working against the vision API — a `claude setup-token` credential does drive `client.messages.create` with images.

```
ANTHROPIC_AUTH_TOKEN=sk-ant-oat01-...   # from `claude setup-token`
```

`load_credentials()` in `02_agent_classify.py` resolves auth and returns the mode; `build_client()` attaches the required `anthropic-beta: oauth-2025-04-20` header in OAuth mode only. Startup prints which mode is active — check that line before trusting a run.

Set **exactly one** credential. If both `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_API_KEY` are present the API rejects the request, so the script drops the API key and warns. The pay-per-token fallback (`ANTHROPIC_API_KEY`, ~$0.35 for all 216 images on Haiku) stays supported if subscription rate limits become a problem.

`claude setup-token` renders an interactive TUI and **cannot run inside a Claude Code session** — it needs a real terminal.

## Analysis framing (the part carrying the marks)

VGG-16 will likely win on raw accuracy. **That is expected and is not the conclusion.** It was fine-tuned on 864 in-domain labelled images; the agent saw zero. A report that says "VGG-16 scored higher, so it's better" underperforms.

Frame it on the real trade-off axes:

| | Claude agent (zero-shot VLM) | VGG-16 (fine-tuned CNN) |
|---|---|---|
| Labelled training data | none | 864 images |
| Setup / training cost | minutes | GPU training run |
| Inference | ~seconds, network-bound, per-image cost | ~ms, local, free after training |
| Determinism | non-deterministic | deterministic |
| Failure mode | degrades, may refuse/hedge | fails confidently |
| Novel classes | works without retraining | needs full retrain |

Highest-value content: the **disagreement set** — images where exactly one branch is right. `03_compare_results.py` already emits the first 15. Open them by eye. Do glacier/mountain and buildings/street confusions dominate? Which branch handles genuinely ambiguous scenes more sensibly? That qualitative pass is what distinguishes the analysis from a metrics dump.

Also report: blank agent predictions (responses that matched no class) are scored as wrong. Say so explicitly rather than dropping them.

---

## OpenClaw workstream

OpenClaw (`npm i -g openclaw`) is a separate open-source agent runtime, not the Claude API. Config lives at `~/.openclaw/openclaw.json` (JSON5).

Model string format is `provider/model`:

```json5
{ agents: { defaults: { model: { primary: "anthropic/claude-haiku-4-5" } } } }
```

### Installed state (verified working)

OpenClaw **2026.5.12** is installed globally. `~/.openclaw/openclaw.json` has `gateway.mode: local`, `bind: loopback`, token auth, `session.dmScope: per-channel-peer`, and `agents.defaults.model.primary: anthropic/claude-haiku-4-5`. An `anthropic:default [anthropic/token]` auth profile exists and **an agent turn on Haiku succeeds** (`openclaw agent --agent main -m "..."`).

The global npm bin is not on the default PATH in this shell — prefix commands with:
`export PATH="$PATH:/c/Users/mushf/AppData/Roaming/npm"`

### Hard-won gotchas — read before touching OpenClaw

- **Anything interactive cannot run in a Claude Code session.** `claude setup-token`, `openclaw models auth paste-token`, `auth login`, and `auth setup-token` all render TUIs / require a TTY. Piping stdin into `paste-token` types the characters but crashes and saves nothing. These must be run by the user in a real terminal.
- **Use `--non-interactive --accept-risk`** for onboarding: `openclaw onboard --non-interactive --accept-risk --mode local`. Plain `setup --non-interactive` refuses without `--accept-risk`.
- **OpenClaw ignores `ANTHROPIC_AUTH_TOKEN` from the environment.** It requires a stored auth profile under `agents/main/agent/`. Setting the env var does nothing.
- **Never pass `--set-default` to an auth command.** It applies the provider's recommendation (`claude-opus-4-7`) and would silently violate the Haiku-only requirement. Re-check `openclaw models list` after any auth change — the model column must stay `anthropic/claude-haiku-4-5`.
- **`cron add --at` takes a bare duration** (`2m`), not `+2m`.
- **The gateway survives `TaskStop`** — that only kills the shell wrapper. Kill the node process by PID (find it with `netstat -ano | grep 18789`).
- **Device scope deadlock — fixed 2026-07-30, but know the shape of it.** Privileged commands (`cron add`, `devices clear`) need `operator.admin`/`operator.pairing`; the CLI device was paired with only `operator.read`/`operator.write`. `devices approve` **cannot** fix this — each connection mints a new pending request id, so the id is always stale, and `--latest` only displays. The fix is offline: stop the gateway, then in `~/.openclaw/devices/paired.json` set `scopes`, `approvedScopes` **and** `tokens.operator.scopes` all to the same four scopes, blank `pending.json` to `{}`, restart. No signature on that table, so hand edits stick. Claude Code's classifier blocks writing those files from either Bash or Edit — **the user must edit them by hand.**
- **`cron runs` requires `--id <job-id>`;** `cron delete` does not take `--id`, and `cron runs` does **not** accept `--json` (only `cron list` does). A one-off job disappears from `cron list` once it has fired, even with `--keep-after-run` — check `cron runs` for the result, not `cron list`. Raw run records are at `~/.openclaw/cron/runs/<job-id>.jsonl`; **read them with `encoding='utf-8'`**, they contain emoji and Python defaults to cp1252 on this machine.
- **Telegram delivery needs an explicit `--to <chatId>` when a job is created from the CLI.** The CLI has no chat context, so delivery resolves `to: null` and the run *succeeds* while the message silently never arrives (`"Delivering to Telegram requires target <chatId>"` in the run record, `deliveryStatus: unknown`). Jobs the agent creates from an actual Telegram conversation resolve the id themselves. Owner chat id: `5235029766`. Also pass `--best-effort-deliver` on the briefing so a delivery hiccup doesn't fail the whole job.
- **Weather: scraping weather sites does not work** — they need JS or block scrapers, and the agent correctly reports failure rather than inventing numbers. Use the open-meteo JSON API (no key required), latitude 23.8103 / longitude 90.4125, `timezone=Asia/Dhaka`. Verified returning live data.
- **Custom skills go in `~/.openclaw/workspace/skills/<name>/SKILL.md`** and are picked up automatically (source shows as `openclaw-workspace`, status `✓ ready`). `openclaw skills install` only pulls from ClawHub, so it is not the route for a local skill.
- **The gateway strips secret-shaped env vars from the agent's exec environment.** `GITHUB_REPO` reaches the agent's shell; `GITHUB_TOKEN` arrives **empty**. Neither the project `.env` nor `~/.openclaw/.env` is exported into that shell as variables — `~/.openclaw/.env` is a *managed-service* env source, consumed at service install, not by a manually started gateway. The working pattern is for the skill to **source `~/.openclaw/.env` itself** at the start of every run. Verified by rate limit: 5000 = authenticated, 60 = not.
- **`$OPENCLAW_STATE_DIR` is empty in the exec environment.** A skill that builds a path from it silently resolves to filesystem root, every state read fails, and the skill takes its first-run branch forever — reporting "baseline established" while hiding real activity. Use literal `$HOME/.openclaw/...` paths in skills.
- **Don't ask Haiku to do bookkeeping in prose.** `github-notify` fetched correctly, wrote state correctly, and *still* reported "no new activity" for a commit it had just fetched. The old/new diff now lives in `openclaw/skills/github-notify/check.py`; `SKILL.md` only tells the model to run it and relay the output. Both failures here were silent, which is the point worth making in the report. **`check.py` needs `python` in the container** — check `openclaw/Dockerfile` before deploying.
- **Repeated `openclaw agent` CLI calls share a session** and the model will replay its previous answer instead of re-polling. Scheduled jobs use `sessionTarget: isolated` and do not have this problem — test features via `cron add --at 45s`, not repeated CLI turns.
- **The agent's persona lives in the workspace, not config:** `IDENTITY.md`, `SOUL.md`, `USER.md` in `~/.openclaw/workspace/`. Ours is **Chela** 🦞. These files are *not* in the repo, so they are wiped by a Render redeploy along with everything else in `~/.openclaw/` — copy them into the image if the persona should survive.

### Security posture (state this in the report, don't hide it)

OpenClaw's own docs warn that *"prompt-injection risk with older/smaller models is often too high"* for tool-enabled agents and to avoid weak model tiers. Haiku is required here anyway, so the mitigations that matter are structural: loopback binding, token auth, single-peer Telegram pairing. `tools.profile` is left at `coding` rather than the docs' hardened `messaging` **deliberately** — tightening it (or applying their `exec: deny` / `group:fs` denies) would break the scheduling and file access the three required features need.

### Features to add (instructor requirement)

1. **Morning briefing** — OpenClaw has native natural-language scheduling; no external cron. Instruct it once in chat. Weather requires a web-search tool call in the scheduled prompt.
2. **Reminders** — persistent memory + scheduling. One-off and recurring both supported via phrasing.
3. **GitHub notifications** — needs a real tool, not chat. Use a GitHub MCP server, or a custom skill against the GitHub REST API with a PAT. Poll commits/PRs on a schedule; message on new review or failed CI.

Delivery channel: Telegram (needs a bot token). Store all tokens as env/secret refs, never inline in committed config.

### Render hosting — known constraints

- **Free tier has no persistent disk.** `~/.openclaw/` — memory, scheduled tasks, auth — is wiped on every redeploy and restart. Scheduled reminders will not survive. Either accept this for the demo, mount a paid disk, or externalise state.
- **Free web services sleep after ~15 min idle.** A cron ping keeps the instance warm; without it, scheduled tasks silently miss their window.
- **Claude CLI credential reuse expects OpenClaw on the same host as the CLI login** — so on Render use a `setup-token` value passed as an env var, not CLI auto-detection.
- Subscription-backed tokens on an always-on server is a grey area and rate-limit behaviour can change without notice. Fine for a short-lived lab demo; not for anything long-running.

Have a **local fallback** ready for the lab exam. Render free tier failing mid-demo is a realistic outcome.

---

## Conventions

- Scripts are numbered by pipeline order; keep that scheme.
- Every script has a module docstring explaining *why*, a `main()`, `argparse` flags with defaults, and exits via `sys.exit("message")` on unrecoverable state. Match this style.
- Fail loudly on anything that would corrupt the comparison; never silently continue.
- `results/*.csv` and `*.png` are gitignored; `comparison_report.md` is committed.
- Windows / PowerShell is the primary shell. Paths in the agent CSV use `\`; `03_compare_results.py` normalises separators — don't assume POSIX paths.
