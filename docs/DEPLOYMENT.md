# Deploying the OpenClaw gateway

Two hosting paths are committed. **Railway is the recommended one**; the Render
blueprint is kept because it works and because the problems it exposed are worth
reporting.

---

## Why Railway rather than Render free

| | Render free | Railway trial |
|---|---|---|
| CPU | ~0.1 core | 2 vCPU |
| RAM | 512 MB | 512 MB |
| Idle behaviour | sleeps after ~15 min | stays up |
| Persistent disk | none (paid only) | volumes available |
| Cost | free | $5 credit, then usage |

The CPU line is the one that decided it. On Render free an agent turn starved the
event loop for over 20 seconds (`eventLoopDelayMaxMs=20199.8`,
`cpuCoreRatio=0.133`). Render's health check times out after 5 seconds, so the
instance was killed and restarted *mid-turn*, and no reply was ever delivered:

```
Instance failed: HTTP health check failed (timed out after 5 seconds)
```

Dropping `healthCheckPath` stops the restart loop, but the underlying slowness
remains — turns still take 30–90 seconds. Railway's 2 vCPU removes the cause
rather than the symptom, and its volumes fix the state problem described below.

---

## Railway

1. **Connect your GitHub account.** Without it Railway applies *network
   restrictions*, and the agent needs outbound access to `api.anthropic.com`,
   `api.telegram.org` and `api.github.com`. Restricted egress produces failures
   that look like auth bugs.
2. **New Project → Deploy from GitHub repo**, select this repository. Railway
   reads `railway.json` and builds `openclaw/Dockerfile` from the repo root,
   which is the context the `COPY openclaw/...` lines expect.
3. **Set the environment variables** (Variables tab):

   | Variable | Value |
   |---|---|
   | `ANTHROPIC_AUTH_TOKEN` | Claude Pro token from `claude setup-token` |
   | `TELEGRAM_BOT_TOKEN` | from @BotFather |
   | `GITHUB_TOKEN` | PAT with read access to the watched repo |
   | `GITHUB_REPO` | `owner/name` |

   Do **not** set `ANTHROPIC_API_KEY` as well — two Anthropic credentials at once
   makes the API reject every request.

4. **Add a volume mounted at `/app/state`.** Strongly recommended: see
   "Ephemeral state" below.
5. Deploy, then watch the log for
   `[entrypoint] mapped ANTHROPIC_AUTH_TOKEN -> ANTHROPIC_OAUTH_TOKEN`.

`$PORT` is injected by Railway and mapped to `OPENCLAW_GATEWAY_PORT` by the
entrypoint, so no port configuration is needed.

---

## Ephemeral state — the thing that actually bites

Everything OpenClaw learns at runtime lives under the state dir (`/app/state`):

- scheduled cron jobs (the morning briefing and the GitHub poll)
- the `github-notify` baseline
- agent memory and session history
- Telegram pairing approvals

**Without a persistent volume, all of it is lost on every restart.** Two
mitigations are already committed, because they cost nothing:

- **Telegram access is config-based, not pairing-based.** `dmPolicy: "allowlist"`
  with `allowFrom` baked into the image, because `pairing approve` writes to a
  store under the state dir and would be forgotten on every restart — leaving the
  bot silently ignoring messages until re-paired by hand.
- **The persona is baked into the image** at `/app/workspace`
  (`IDENTITY.md`, `SOUL.md`, `USER.md`), deliberately outside the state dir.

Scheduled jobs cannot be handled this way — they are runtime state. With a volume
they persist. Without one, recreate them after each restart by messaging the bot:

> Every day at 7:30am, send me a morning briefing: Dhaka weather from the
> open-meteo API, my reminders for the day, and the date.

> Every 30 minutes, run your github-notify check and only message me if there is
> new activity.

---

## Credentials: the non-obvious part

OpenClaw recognises exactly two environment variables for Anthropic:

```js
CORE_PROVIDER_AUTH_ENV_VAR_CANDIDATES = {
  anthropic: ["ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_API_KEY"], ...
```

`ANTHROPIC_AUTH_TOKEN` — the name used by the Anthropic SDK, by this project's
`.env`, and by `scripts/02_agent_classify.py` — is **not** one of them. Setting
only that produces `No API key found for provider "anthropic"` on every turn.
The entrypoint maps it to `ANTHROPIC_OAUTH_TOKEN`, since a Pro subscription
token (`sk-ant-oat01-…`) is an OAuth credential.

This is also why it worked locally and not in a container: locally OpenClaw
authenticates from a stored auth profile written by an interactive
`openclaw models auth setup-token` run, not from the environment at all. Writing
`auth-profiles.json` and `auth-state.json` into the agent dir by hand does **not**
substitute for it — this version authenticates from `openclaw-agent.sqlite` and
ignores static JSON profiles.

Using a subscription token on an always-on server is a grey area. It is fine for
a short-lived demo; a funded `ANTHROPIC_API_KEY` is the durable answer.

---

## Running two gateways at once — don't

Both instances long-poll the same bot token and fight over updates, producing
dropped and duplicated messages that look like a broken deployment. Before
deploying, stop the local gateway; before running locally, pause the hosted one.

## Local fallback

Keep this rehearsed for the lab exam. From the repo root in Git Bash:

```sh
set -a; . ./.env; set +a
export PATH="$PATH:/c/Users/mushf/AppData/Roaming/npm"
openclaw gateway
```

Sourcing `.env` is not optional — without it Telegram and GitHub both go quiet
with no obvious error.
