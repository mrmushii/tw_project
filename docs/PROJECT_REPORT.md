# Zero-Shot Vision Agent vs Fine-Tuned CNN: A Comparative Study on Scene Classification

**Working document** — source material for the project report and the presentation.
Part A is the reproducible method, Part B the results and analysis, Part C the slide
outline, Part D the OpenClaw deliverable, Part E remaining work.

Every number in Part B is measured from this project's own runs, not quoted from
literature. Figures come from `results/comparison_report.md` and
`results/confusion_matrices.png`.

---

## Abstract (draft — tighten to your word limit)

We compare two approaches to six-class natural-scene classification on an identical
216-image test set: a zero-shot vision-language agent (Claude Haiku 4.5, driven
through the Anthropic Messages API) and a VGG-16 convolutional network fine-tuned by
transfer learning on 864 labelled images from the same distribution.

The agent achieved **91.7%** accuracy (macro-F1 0.916); VGG-16 achieved **90.3%**
(macro-F1 0.903). A McNemar exact test on the 25 discordant predictions gives
**p = 0.690**, so the 1.4-point gap is not statistically significant — the two methods
are **statistically indistinguishable in accuracy**. The substantive finding is that
they are *not* equivalent in behaviour: their errors are structurally different. The
agent commits **one-directional semantic errors**, consistently collapsing a specific
class into its superordinate category (glacier → mountain, 6 errors; mountain → glacier,
0). VGG-16 commits **symmetric perceptual errors** on the same pair (5 in each
direction), indicating failure to discriminate visual features rather than a category
judgement. The two systems are complementary: only 7 of 216 images defeat both, and an
oracle selecting the better branch per image would reach 96.8%.

We conclude that a zero-shot agent matched a fine-tuned CNN on this task **at zero
labelling cost**, and that method selection should be driven by the availability of
labelled data, latency and cost constraints, and the kind of error a deployment can
tolerate — not by accuracy alone.

---

# Part A — Method (every step, reproducibly)

## A.0 Environment

| Item | Value |
|---|---|
| OS / shell | Windows 11, PowerShell |
| Python deps | `anthropic`, `python-dotenv`, `pillow`, `pandas`, `scikit-learn`, `matplotlib`, `kagglehub`, `tqdm` |
| Agent model | `claude-haiku-4-5` |
| CNN training | Kaggle Notebooks, free GPU (TensorFlow/Keras) |
| Repo layout | `data/`, `scripts/`, `kaggle/`, `results/`, `openclaw/`, `docs/` |

TensorFlow is deliberately **not** installed locally — VGG-16 trains on Kaggle's free
GPU. This keeps the local environment small and is worth stating as a practical
constraint in the report.

## A.1 Dataset acquisition

**Dataset:** Intel Image Classification (Kaggle: `puneet6060/intel-image-classification`).
Six natural-scene classes: `buildings, forest, glacier, mountain, sea, street`.

Chosen because the classes contain **two genuinely overlapping pairs** —
buildings/street and glacier/mountain. That overlap is what makes the error analysis
in Part B possible; a trivially separable dataset would have produced two near-perfect
scores and nothing to discuss.

Downloaded via `kagglehub` inside `scripts/01_prepare_dataset.py`. The archive unzips
to a nested layout (`seg_train/seg_train/<class>/`), so the script searches recursively
for each class folder and picks the candidate containing the most images.

## A.2 Sampling and the shared split

```powershell
python scripts/01_prepare_dataset.py          # 180/class, 80/20, seed 42
python scripts/check_split.py                 # balance + leakage verification
```

| Parameter | Value |
|---|---|
| Sampled per class | 180 |
| Split | 80 / 20 |
| Random seed | 42 (fixed → reproducible) |
| Train | 144 per class → **864 total** |
| Test | 36 per class → **216 total** |

Three design decisions worth defending in the report:

1. **Perfect class balance** (36 test images per class). Accuracy is therefore not
   inflated by a dominant class, and macro-F1 ≈ accuracy, as observed.
2. **One shared test set.** Both branches are scored on exactly the same 216 images.
   This is the single control that makes the comparison valid. VGG-16 trains on
   `train/`; the agent never sees `train/` at all — it is zero-shot by construction.
3. **Filenames prefixed with their class** (`forest_123.jpg`). The basename becomes a
   globally unique key, which later lets the agent's absolute Windows paths be aligned
   against Kaggle's POSIX-style paths.

The script deletes and rebuilds both splits on each run, so it is deterministic and
leak-free — but re-running it after collecting predictions would orphan them.

## A.3 Credentials

Two options exist; the project used the first.

**Option A — Claude Pro subscription (used).** Run in a real terminal (it renders an
interactive prompt and cannot run inside an automated session):

```powershell
claude setup-token          # yields sk-ant-oat01-...
```

Store as `ANTHROPIC_AUTH_TOKEN` in `.env`. OAuth tokens travel on
`Authorization: Bearer` and additionally require the header
`anthropic-beta: oauth-2025-04-20`, which `build_client()` attaches in OAuth mode only.

**Option B — pay-per-token API key.** `ANTHROPIC_API_KEY` from the Anthropic Console.
Cost for this workload: 216 images × ~1,600 image tokens ≈ 350K input tokens on Haiku
≈ **US$0.35**.

**Set exactly one.** If both are present the API rejects every request, so
`load_credentials()` drops the API key and warns. During this project an existing key
was found to be valid but unfunded (`"credit balance is too low"`), which is what
motivated Option A.

`.env` is gitignored; `.env.example` documents both paths with no real values.

## A.4 Agent branch — zero-shot classification

```powershell
python scripts/02_agent_classify.py --limit 1     # auth gate
python scripts/02_agent_classify.py --limit 10    # smoke test
python scripts/02_agent_classify.py               # full run (resumes)
```

Each test image is base64-encoded and sent with a deliberately constrained prompt:

```
Classify this image into exactly one of these scene categories.
Reply with ONLY one of these exact lowercase words, nothing else:
buildings, forest, glacier, mountain, sea, street
```

`max_tokens=16` — one word is sufficient, and a low ceiling further discourages prose.

Engineering decisions worth reporting:

- **Resumable and crash-safe.** Each row is flushed to CSV immediately, and filepaths
  already present are skipped. An interrupted run never re-bills or duplicates work.
- **Normalisation with a fallback.** Replies are matched against the known class set;
  if a reply contains extra words, the first class name appearing in it is taken.
  Unrecognised replies are stored verbatim in `raw_response` and left blank in
  `predicted_label` rather than silently guessed.
- **Retries.** The SDK auto-retries 429/5xx with exponential backoff (`max_retries=5`),
  plus a 0.3 s inter-call delay.

**Measured outcome:** 216/216 images classified, **0 malformed responses** and
**0 blank predictions**. Every reply was a bare class word. Prompt constraint is worth
one sentence in the report, because unparseable free-text output is the usual failure
mode for LLM classification and it did not occur here.

**Throughput:** ~1.5 s per image (10 images in 14.9 s), so ≈ 5.4 minutes wall-clock for
216. Network-bound, not compute-bound.

## A.5 VGG-16 branch — transfer learning on Kaggle

Packaged the split for upload:

```python
shutil.make_archive('splits', 'zip', root_dir='.', base_dir='splits')   # 16 MB, 1080 images
```

Steps:

1. Kaggle → **New Dataset** → upload `data/splits.zip` → title it **`tw-project-splits`**
   (the notebook hardcodes `/kaggle/input/tw-project-splits/splits`).
2. **New Notebook** → upload `kaggle/vgg16_train.ipynb` → attach the dataset.
3. **Settings → Accelerator → GPU.** Without it, training takes hours instead of minutes.
4. Run cells 1–4; cell 4 asserts the paths exist and prints `class_indices` and sample
   counts. Confirm **864 train / 216 test** and all six classes before training.
5. `EPOCHS = 2` smoke run, then **15** for the real run.
6. Download `vgg16_predictions.csv` from the output panel into `results/`.

| Hyperparameter | Value |
|---|---|
| Base | VGG-16, ImageNet weights, `include_top=False` |
| Base layers | **Frozen** (feature extraction, not full fine-tuning) |
| Input size | 224 × 224 (VGG-16 native) |
| Preprocessing | `vgg16.preprocess_input` |
| Batch size | 32 |
| Epochs | 15 |
| Head | New dense classifier, 6-way softmax |

Two notebook details that are load-bearing:

- `shuffle=False` on the test generator. Shuffling would desynchronise
  `test_generator.filenames` from the prediction array and silently corrupt every label.
- Predictions are exported as `test/<class>/<file>` — a stable cross-machine key,
  deliberately not an absolute path.

**Freezing the base is a defensible choice to state explicitly:** with only 144 training
images per class, unfreezing VGG-16's ~14.7M convolutional parameters would very likely
overfit. This is also an honest limitation — a deeper fine-tune with more data might
close or reverse the gap, and the report should say so.

## A.6 Comparison

```powershell
python scripts/03_compare_results.py
```

Outputs `results/comparison_report.md` and `results/confusion_matrices.png`.

The script **refuses to produce metrics** unless the comparison is valid. It exits
fatally if:

- the two CSVs do not cover an identical set of image keys,
- any image has a different `true_label` between the two files,
- duplicate keys exist within either file.

Alignment is on the class-prefixed basename, which bridges the two path formats.
This validation is worth describing in the methodology — it is the mechanism that
guarantees a fair comparison rather than an assumption of one.

**Verified:** aligned on 216 shared test images, no mismatches.

## A.7 Statistical testing

Accuracy differences on a 216-image test set are easy to over-read, so:

- **McNemar exact test** on the discordant pairs (the correct paired test when two
  models are evaluated on the same items — an unpaired two-proportion test would be
  wrong here).
- **Wilson score 95% confidence intervals** on each accuracy.
- **Oracle ensemble upper bound** — accuracy if a perfect arbiter chose the better
  branch per image; quantifies complementarity.

---

# Part B — Results and analysis

## B.1 Headline metrics

| Branch | Accuracy | Macro-F1 | 95% CI (Wilson) | Labelled images used |
|---|---|---|---|---|
| Agent — Haiku 4.5, zero-shot | **0.917** (198/216) | 0.916 | [0.872, 0.947] | **0** |
| VGG-16 — fine-tuned | 0.903 (195/216) | 0.903 | [0.856, 0.936] | 864 |

## B.2 The gap is not statistically significant

| Quantity | Value |
|---|---|
| Agent correct, VGG-16 wrong | 14 |
| VGG-16 correct, agent wrong | 11 |
| Discordant pairs | 25 |
| **McNemar exact, two-sided** | **p = 0.690** |

p = 0.690 is nowhere near any conventional threshold, and the two confidence intervals
overlap across almost their entire range.

> **State this plainly and do not overclaim.** The agent scored higher by three images.
> That is sampling noise, not a demonstrated advantage. The supportable claim is that
> the two methods are **statistically indistinguishable in accuracy on this test set**.
>
> This is a stronger result than a narrow win would be: the agent reached parity with a
> fine-tuned CNN **using no labelled training data at all**, against VGG-16's 864
> labelled images. The interesting axis is not which is more accurate — it is what each
> costs to obtain and how each fails.

## B.3 Per-class performance

**Agent (Haiku 4.5, zero-shot)**

| Class | Precision | Recall | F1 |
|---|---|---|---|
| buildings | 1.000 | 0.778 | 0.875 |
| forest | 0.947 | 1.000 | 0.973 |
| glacier | 0.968 | 0.833 | 0.896 |
| mountain | 0.829 | 0.944 | 0.883 |
| sea | 1.000 | 0.944 | 0.971 |
| street | 0.818 | 1.000 | 0.900 |
| **macro avg** | **0.927** | **0.917** | **0.916** |

**VGG-16 (fine-tuned)**

| Class | Precision | Recall | F1 |
|---|---|---|---|
| buildings | 0.875 | 0.972 | 0.921 |
| forest | 0.972 | 0.972 | 0.972 |
| glacier | 0.784 | 0.806 | 0.795 |
| mountain | 0.861 | 0.861 | 0.861 |
| sea | 0.971 | 0.944 | 0.958 |
| street | 0.969 | 0.861 | 0.912 |
| **macro avg** | **0.905** | **0.903** | **0.903** |

**Recall, side by side**

| Class | Agent | VGG-16 | Δ (VGG − agent) |
|---|---|---|---|
| buildings | 0.778 | **0.972** | **+0.194** |
| forest | **1.000** | 0.972 | −0.028 |
| glacier | **0.833** | 0.806 | −0.028 |
| mountain | **0.944** | 0.861 | −0.083 |
| sea | 0.944 | 0.944 | 0.000 |
| street | **1.000** | 0.861 | **−0.139** |

The two largest deltas point in **opposite directions on the same confusable pair**:
VGG-16 is far better at `buildings`, the agent is far better at `street`. This is the
first sign of the mirror-bias structure developed next.

## B.4 Error structure — the principal finding

**Complete error profiles**

| Agent — 18 errors | n |
|---|---|
| buildings → street | 8 |
| glacier → mountain | 6 |
| mountain → forest | 2 |
| sea → mountain | 1 |
| sea → glacier | 1 |

| VGG-16 — 21 errors | n |
|---|---|
| glacier → mountain | 5 |
| mountain → glacier | 5 |
| street → buildings | 5 |
| sea → glacier | 2 |
| buildings → street | 1 |
| *(remaining scattered)* | 3 |

**Directional comparison**

| Pair | Agent | VGG-16 |
|---|---|---|
| buildings → street | **8** | 1 |
| street → buildings | **0** | **5** |
| glacier → mountain | **6** | 5 |
| mountain → glacier | **0** | **5** |

Three conclusions follow.

### (1) The biases are mirror images

On buildings/street the agent collapses `buildings` **into** `street` (8 errors, 0 in
reverse). VGG-16 does the opposite, collapsing `street` **into** `buildings` (5 errors,
1 in reverse). Same ambiguous boundary, opposite direction. Their per-class recall
deltas in B.3 are this same fact viewed from the other side.

### (2) Semantic error vs perceptual error

This is the sharpest available distinction, and the report's strongest point.

On glacier/mountain the agent's errors are **strictly one-directional**: 6 glacier→mountain,
**0** mountain→glacier. A model guessing between two visually similar classes would err in
both directions. A strictly one-way error means a *consistent category judgement*: a glacier
scene is a kind of mountain scene, so where both labels are defensible the agent selects
the superordinate term. Its errors are **semantic** — a taxonomy disagreement with the
dataset's labelling convention, and therefore predictable and correctable by prompt
(e.g. defining the intended boundary between the classes).

VGG-16's errors on the same pair are **symmetric**: 5 each way. That is the signature of
**perceptual** failure — the learned features do not separate the classes, so errors
scatter in both directions. Not predictable from the label semantics, and correctable
only with more data, augmentation, or a deeper fine-tune.

Two systems with near-identical accuracy are therefore failing for entirely different
reasons, with different remedies. **Accuracy alone conceals this completely** — which is
itself a methodological argument for reporting confusion structure rather than a single
score.

### (3) The methods are complementary

| Outcome | Count | Share |
|---|---|---|
| Both correct | 184 | 85.2% |
| Agent only correct | 14 | 6.5% |
| VGG-16 only correct | 11 | 5.1% |
| **Both wrong** | **7** | **3.2%** |

Only 7 of 216 images defeat both. An **oracle ensemble** — a perfect arbiter choosing
the better branch per image — would reach **209/216 = 96.8%**, roughly 5 points above
either branch alone. The residual 3.2% is the irreducible portion for this pair of models.

Notably **4 of those 7 are `glacier`** images that both models called `mountain` (or
`forest`). When two independent systems with unrelated inductive biases agree on the same
"wrong" answer, dataset **label noise** becomes a plausible explanation. Recommend
inspecting these by eye and noting the possibility rather than assuming both models failed:

```
glacier_2113.jpg   glacier_4210.jpg   glacier_7721.jpg   glacier_8927.jpg
buildings_7084.jpg sea_17759.jpg      sea_6432.jpg
```

## B.5 Cost and operational comparison

Measured or directly derived from this project:

| Dimension | Agent (Haiku, zero-shot) | VGG-16 (fine-tuned) |
|---|---|---|
| Labelled training images | **0** | 864 |
| Training time | none | GPU training run (Kaggle) |
| Setup effort | prompt + API call | dataset upload, generators, training loop |
| Inference latency | ~1.5 s / image (network-bound) | milliseconds / image (local GPU) |
| Marginal cost | per image, indefinitely (~$0.0016 on Haiku) | free after training |
| Determinism | non-deterministic | deterministic |
| Failure mode | semantic, one-directional, predictable | perceptual, symmetric |
| Adding a new class | edit the prompt | relabel + retrain |
| Offline / air-gapped | impossible | yes |
| Interpretability | can be asked to explain | confidence vector only |

The trade-off is not accuracy. **It is labelled-data cost and setup time versus
per-image inference cost, latency, and determinism.** Batch classification of a fixed
label set at high volume favours the CNN. Low volume, no labelled data, or a label set
expected to change favours the agent.

## B.6 Which method worked better, and why

**Accuracy: neither.** 0.917 vs 0.903, p = 0.690 — statistically indistinguishable.

**Why the agent did as well as it did.** It inherits scene understanding from
large-scale multimodal pretraining, so all six categories are already familiar concepts.
The task — assigning a common natural scene to one of six common labels — sits squarely
inside that prior, needing no task-specific learning. Its remaining errors are not
perceptual failures but disagreements about category boundaries.

**Why VGG-16 did not clearly win despite supervision.** Two limits. First, 144 training
images per class is thin, so only the classifier head could be trained; the frozen
ImageNet features were never adapted to this dataset. Second, those generic features
genuinely do not separate glacier from mountain — visually near-identical, and the
symmetric 5/5 confusion is the direct evidence.

**Where each is actually better.** VGG-16 on `buildings` (+0.194 recall) — supervision
taught it this dataset's specific buildings/street convention, which the agent must
infer. The agent on `street` (+0.139) and `mountain` (+0.083), where its broader semantic
prior generalises better than 144 examples.

**Recommendation.** With no labelled data, or a label set expected to change, the
zero-shot agent is the better engineering choice — comparable accuracy at zero labelling
cost. With abundant labelled data and high inference volume, the CNN wins on latency,
marginal cost, determinism, and offline capability. For maximum accuracy, combine them:
the 96.8% oracle bound shows substantial complementary signal, and the agent's *predictable*
directional bias could arbitrate VGG-16's *symmetric* confusions.

## B.7 Limitations (include these — they earn credit)

1. **Single test set of 216 images.** ±3-point CIs; small differences are unresolvable.
   No cross-validation and no repeated runs.
2. **No repeated agent runs.** The agent is non-deterministic; run-to-run variance was
   not measured. A 3–5 run mean would strengthen the comparison.
3. **VGG-16 base frozen.** A full fine-tune with more data might change the outcome.
   The comparison is against feature-extraction transfer learning specifically.
4. **One model per family.** Haiku is the *cheapest* tier; a larger model would likely
   score higher. Similarly VGG-16 is a 2014 architecture — ResNet or EfficientNet would
   be stronger baselines.
5. **Prompt not systematically ablated.** One constrained prompt was used. Class
   definitions in the prompt would likely reduce the semantic errors in B.4(2), and that
   remains untested.
6. **Possible label noise** in the 7 both-wrong images, not verified by manual inspection.
7. **Cost figures are list prices** at time of writing, not negotiated rates.

## B.8 Future work

- Prompt ablation targeting the one-directional semantic errors: define the
  buildings/street and glacier/mountain boundaries explicitly and re-measure.
- Repeated agent runs to quantify non-determinism.
- Implement the ensemble — agreement-plus-arbitration — and test against the 96.8% oracle.
- Ask the agent for a one-sentence justification per image; use it to audit whether its
  errors really are taxonomy disagreements as B.4(2) argues.
- Swap VGG-16 for ResNet-50 / EfficientNet, and unfreeze with more data.
- Manually inspect the 7 both-wrong images to test the label-noise hypothesis.

---

# Part C — Presentation outline

Approximately 14 slides. Speaker notes marked ▸.

**1. Title**
Zero-Shot Vision Agent vs Fine-Tuned CNN — Scene Classification. Name, course, date.

**2. Research question**
Can a zero-shot vision-language agent match a supervised CNN — and if the scores tie,
what actually differs?
▸ Frame it as a comparison of *methods*, not a contest.

**3. Dataset**
Intel Image Classification, 6 classes, sample grid of images.
Chosen for two genuinely overlapping pairs: buildings/street, glacier/mountain.
▸ The overlap is what makes the error analysis possible.

**4. Experimental design**
Diagram: 180/class → 80/20 split → **864 train / 216 test**. VGG-16 sees train; agent
sees nothing. Both scored on the same 216.
▸ One shared test set is the control that makes this valid.

**5. Branch 1 — the agent**
Haiku 4.5, constrained prompt, `max_tokens=16`, resumable CSV pipeline.
**0 malformed responses / 216.**
▸ Unparseable output is the usual LLM-classification failure; it didn't happen.

**6. Branch 2 — VGG-16**
ImageNet weights, frozen base, new 6-way head, 224×224, 15 epochs, Kaggle GPU.
▸ Base frozen because 144 images/class would overfit 14.7M parameters.

**7. Headline results**
0.917 vs 0.903 — with **0 vs 864** labelled images in a highlighted column.
▸ Pause on the labelled-data column, not the accuracy column.

**8. …but the gap is not significant**
McNemar **p = 0.690**; overlapping CIs.
▸ Say explicitly: we are *not* claiming the agent won. Three images is noise.

**9. Confusion matrices side by side**
`results/confusion_matrices.png`.
▸ Point out the off-diagonal cells sit in *different* places.

**10. Finding 1 — mirror-image biases**
The directional table. Agent: buildings→street 8, reverse 0. VGG-16: street→buildings 5,
reverse 1.
▸ Same boundary, opposite direction.

**11. Finding 2 — semantic vs perceptual** ★ *strongest slide*
Agent glacier→mountain **6 / 0** — one-directional ⇒ a category judgement.
VGG-16 **5 / 5** — symmetric ⇒ feature-discrimination failure.
▸ Identical accuracy, different causes, different fixes. Accuracy alone hides this.

**12. Finding 3 — complementary**
184 both / 14 agent-only / 11 VGG-only / **7 both** → oracle **96.8%**.
4 of the 7 are glacier: possible label noise.
▸ Two independent systems agreeing on a wrong answer suggests the label, not the models.

**13. Trade-off table**
The B.5 table. Labelled data, latency, marginal cost, determinism, new classes, offline.
▸ The real decision variable is data availability, not accuracy.

**14. Conclusion + future work**
Parity at zero labelling cost; choose by constraints; ensemble is the accuracy path.
Future: prompt ablation, repeated runs, stronger CNN backbone.

**Appendix slides** — full per-class tables; limitations; OpenClaw architecture.

### Delivery notes
- Slides 8 and 11 are what distinguish this from a metrics dump. Don't rush them.
- Anticipated question: *"Why is Haiku's accuracy higher if it wasn't trained?"* →
  large-scale multimodal pretraining already covers these six everyday categories; the
  task falls inside its prior. VGG-16 had to learn from 144 images per class.
- Anticipated question: *"So the agent is better?"* → No. Statistically tied. It is
  better *per labelled image*, which is a different and more useful claim.

---

# Part D — OpenClaw deliverable

OpenClaw is an open-source personal AI agent that runs locally, created by Peter
Steinberger and maintained under the OpenClaw Foundation. It communicates across
messaging channels, controls browsers and files, holds persistent memory, and is
extensible with skills. This project runs it on **Haiku 4.5**, the same model as the
agent branch above — a deliberate consistency choice.

## D.1 Steps completed

**Install**

```powershell
npm i -g openclaw
```

**Configure the model** in `~/.openclaw/openclaw.json` (JSON5) — the format is
`provider/model`:

```json5
{ agents: { defaults: { model: { primary: "anthropic/claude-haiku-4-5" } } } }
```

**Authenticate** — `openclaw onboard`, then either "Anthropic API key" or "Claude CLI"
to reuse the Pro subscription login. Verify:

```powershell
openclaw models list --provider anthropic
```

**Deployment artifacts written** (all validated, no secrets committed):

| File | Purpose |
|---|---|
| `openclaw/openclaw.json` | Haiku primary, Telegram channel, skills dir; every credential from env |
| `openclaw/Dockerfile` | node:22-slim + global install; maps Render's `$PORT` → `OPENCLAW_GATEWAY_PORT` |
| `render.yaml` | Free plan, health check `/v1/models`, four `sync:false` env vars |
| `openclaw/skills/github-notify/SKILL.md` | Custom skill, valid YAML frontmatter |

## D.2 Architecture notes for the report

- **Gateway** — single multiplexed process for routing, control plane, and channels.
  Default port **18789**, overridable via `OPENCLAW_GATEWAY_PORT`. Exposes
  OpenAI-compatible HTTP endpoints including `GET /v1/models`, used here as the health
  check and keep-alive target.
- **Telegram uses long polling** by default. No inbound webhook is required, which is
  precisely what makes free-tier hosting viable.
- **Skills** are directories containing a `SKILL.md` with YAML frontmatter (`name`,
  `description`) and a markdown body, discovered from configured roots. Loaded on
  demand — progressive disclosure keeps the base context small.
- **State** lives under `OPENCLAW_STATE_DIR`: memory, schedules, channel pairings.

## D.3 Three added features (instructor requirement)

| # | Feature | Mechanism | Code required |
|---|---|---|---|
| 1 | Reminders | Native scheduling + persistent memory | None — usage only |
| 2 | Morning briefing | One scheduled natural-language instruction; web search for weather | None |
| 3 | GitHub notifications | Custom skill calling the GitHub REST API | `SKILL.md` + PAT |

**Why the ordering matters:** reminders are implemented first because they exercise the
scheduling and memory stack with no code. If scheduling is broken, the briefing cannot
work either — so this is the cheapest possible validation of the shared dependency.

The `github-notify` skill polls commits, open PRs, PR reviews, and failed GitHub Actions
runs, tracking already-reported items in a state file so a scheduled run stays silent
when nothing has changed. It reports failures first and never echoes the token.

## D.4 Known constraints — document, don't hide

| Constraint | Consequence | Mitigation |
|---|---|---|
| Render free tier has **no persistent disk** | `OPENCLAW_STATE_DIR` wiped on every restart/redeploy — schedules, memory, pairings lost | Re-seed before the demo; a paid disk is the real fix |
| Free services **sleep after ~15 min idle** | A sleeping instance silently misses scheduled tasks | External cron pings `/v1/models` every 10 min |
| Claude CLI credential reuse expects **same host** | Cannot reuse a laptop login from Render | Use a `setup-token` value as an env var |
| Subscription tokens on an always-on server | Grey area; rate-limit behaviour may change | Acceptable for a short-lived demo, not production |

Presenting these as understood engineering trade-offs is stronger than presenting a
deployment that appears flawless.

---

# Part E — Remaining work

| # | Task | Detail |
|---|---|---|
| 1 | Telegram bot | `/newbot` via @BotFather → `TELEGRAM_BOT_TOKEN` |
| 2 | Run gateway locally | `openclaw gateway`, then `openclaw pairing list telegram` → `openclaw pairing approve telegram <CODE>` |
| 3 | Verify reminders | Set one 2 minutes out; confirm it fires. Validates the scheduling stack |
| 4 | Verify morning briefing | Schedule 8am calendar/reminder summary via Telegram; add web search for weather |
| 5 | GitHub PAT | `repo` scope → `GITHUB_TOKEN`, `GITHUB_REPO`; test the skill against a real repo |
| 6 | Push to GitHub | Required for Render blueprint deploy |
| 7 | Deploy on Render | New → Blueprint → set the four `sync:false` vars |
| 8 | Confirm deployment | `openclaw gateway status`; health check returns 200 |
| 9 | Keep-alive cron | cron-job.org → `https://<service>.onrender.com/v1/models` every 10 min |
| 10 | Local fallback | Rehearse running locally in case free tier fails mid-demo |
| 11 | Optional — strengthen study | Repeated agent runs; prompt ablation on the two confusable pairs |
| 12 | Write final artifacts | Report from Parts A/B, slides from Part C |

## Assets ready to use

| Asset | Path |
|---|---|
| Confusion matrices figure | `results/confusion_matrices.png` |
| Generated metrics report | `results/comparison_report.md` |
| Agent predictions (216) | `results/agent_predictions.csv` |
| VGG-16 predictions (216) | `results/vgg16_predictions.csv` |
| Packaged dataset for Kaggle | `data/splits.zip` (16 MB) |
| Repo conventions / guardrails | `CLAUDE.md` |
