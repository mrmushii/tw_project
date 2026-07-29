# Agent (Claude API) vs VGG-16 — Multi-Class Image Classification

Compares two approaches to multi-class image classification on a shared test split:

1. **Agent branch** — the Claude API vision model classifies each test image (runs locally).
2. **VGG-16 branch** — a fine-tuned VGG-16 CNN, trained on Kaggle (free GPU).

Both are evaluated on the **same** `data/splits/test/` set — that shared test set is what makes the comparison fair.

## Dataset
Intel Image Classification (Kaggle) — 6 classes: `buildings, forest, glacier, mountain, sea, street`.

## Where each step runs
| # | Step | Where |
|---|------|-------|
| 1 | Scaffold project | Local |
| 2 | Prepare dataset + shared test split | Local — `scripts/01_prepare_dataset.py` |
| 3 | Agent classification (Claude API) | Local — `scripts/02_agent_classify.py` |
| 4 | VGG-16 fine-tuning | **Kaggle (GPU)** — `kaggle/vgg16_train.ipynb` |
| 5 | Compare results | Local — `scripts/03_compare_results.py` |
| 6 | Report & presentation | Write-up |

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env   # then paste your real ANTHROPIC_API_KEY into .env
```

`.env` holds your `ANTHROPIC_API_KEY` and is gitignored — never commit it.

## Layout
```
data/raw/        downloaded dataset
data/splits/     train/ and test/ class folders (created in Step 2)
scripts/         local pipeline scripts
kaggle/          notebook uploaded to Kaggle (not run locally)
results/         prediction CSVs + comparison_report.md
```
