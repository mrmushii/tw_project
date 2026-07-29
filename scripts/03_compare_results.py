"""
Step 5 — Comparison & evaluation.

Loads both prediction CSVs, confirms they cover the same test images, computes
per-branch metrics (accuracy, per-class precision/recall/F1, macro-F1, confusion
matrix), plots the two confusion matrices side by side, and writes a markdown
report ready to drop into the final write-up.

Alignment: the agent CSV stores absolute local paths; the VGG-16 CSV stores
'test/<class>/<file>'. Step 1 prefixed every filename with its class, so the
basename (e.g. 'forest_123.jpg') is a unique shared key. We align on basename and
loudly flag any mismatch — this must be caught, not silently ignored.

Usage:
    python scripts/03_compare_results.py

Needs results/agent_predictions.csv and results/vgg16_predictions.csv.
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT_ROOT / "results"
AGENT_CSV = RESULTS / "agent_predictions.csv"
VGG_CSV = RESULTS / "vgg16_predictions.csv"
REPORT_MD = RESULTS / "comparison_report.md"

CLASSES = ["buildings", "forest", "glacier", "mountain", "sea", "street"]


def key_of(filepath: str) -> str:
    """Basename key, tolerant of both '\\' and '/' separators."""
    return filepath.replace("\\", "/").rsplit("/", 1)[-1]


def load(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"Missing {name}: {path}")
    df = pd.read_csv(path).fillna({"predicted_label": ""})
    df["key"] = df["filepath"].map(key_of)
    if df["key"].duplicated().any():
        dupes = df.loc[df["key"].duplicated(), "key"].tolist()[:5]
        sys.exit(f"[FATAL] Duplicate image keys in {name}: {dupes} ...")
    return df


def evaluate(y_true, y_pred, title: str) -> dict:
    from sklearn.metrics import (
        accuracy_score, precision_recall_fscore_support,
        f1_score, confusion_matrix, classification_report,
    )
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=CLASSES)
    report = classification_report(
        y_true, y_pred, labels=CLASSES, zero_division=0, digits=3
    )
    return {"title": title, "acc": acc, "macro_f1": macro_f1, "cm": cm, "report": report}


def plot_confusions(agent_eval, vgg_eval, out_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, ev in zip(axes, (agent_eval, vgg_eval)):
        disp = ConfusionMatrixDisplay(confusion_matrix=ev["cm"], display_labels=CLASSES)
        disp.plot(ax=ax, cmap="Blues", colorbar=False, xticks_rotation=45)
        ax.set_title(f"{ev['title']}\nacc={ev['acc']:.3f}  macro-F1={ev['macro_f1']:.3f}")
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def main() -> None:
    agent = load(AGENT_CSV, "agent_predictions.csv")
    vgg = load(VGG_CSV, "vgg16_predictions.csv")

    # Confirm identical test sets — flag loudly.
    a_keys, v_keys = set(agent["key"]), set(vgg["key"])
    if a_keys != v_keys:
        only_a = sorted(a_keys - v_keys)[:5]
        only_v = sorted(v_keys - a_keys)[:5]
        print("[FATAL] The two CSVs do NOT cover the same test images.")
        print(f"  agent-only ({len(a_keys - v_keys)}): {only_a} ...")
        print(f"  vgg-only   ({len(v_keys - a_keys)}): {only_v} ...")
        sys.exit("Fix the split/prediction mismatch before trusting any metric.")

    # Merge on key so true labels are cross-checked too.
    merged = agent.merge(vgg, on="key", suffixes=("_agent", "_vgg"))
    mismatched_truth = merged[merged["true_label_agent"] != merged["true_label_vgg"]]
    if len(mismatched_truth):
        sys.exit(
            f"[FATAL] {len(mismatched_truth)} image(s) have different true labels between "
            f"the two CSVs — the splits are not the same. First: "
            f"{mismatched_truth['key'].tolist()[:5]}"
        )

    y_true = merged["true_label_agent"].tolist()
    agent_eval = evaluate(y_true, merged["predicted_label_agent"].tolist(), "Agent (Claude API)")
    vgg_eval = evaluate(y_true, merged["predicted_label_vgg"].tolist(), "VGG-16 (fine-tuned)")

    print(f"Aligned on {len(merged)} shared test images.\n")
    for ev in (agent_eval, vgg_eval):
        print(f"=== {ev['title']} ===")
        print(f"accuracy={ev['acc']:.3f}  macro-F1={ev['macro_f1']:.3f}")
        print(ev["report"])
        print()

    out_png = RESULTS / "confusion_matrices.png"
    plot_confusions(agent_eval, vgg_eval, out_png)
    print(f"Saved confusion matrices: {out_png}")

    write_report(merged, agent_eval, vgg_eval, out_png)
    print(f"Wrote report: {REPORT_MD}")


def write_report(merged, agent_eval, vgg_eval, png_path: Path) -> None:
    n = len(merged)
    blank_agent = int((merged["predicted_label_agent"] == "").sum())

    lines = [
        "# Agent (Claude API) vs VGG-16 — Comparison Report\n",
        f"Both branches evaluated on the **same {n} test images**.\n",
        "## Headline metrics\n",
        "| Branch | Accuracy | Macro-F1 |",
        "|---|---|---|",
        f"| Agent (Claude API) | {agent_eval['acc']:.3f} | {agent_eval['macro_f1']:.3f} |",
        f"| VGG-16 (fine-tuned) | {vgg_eval['acc']:.3f} | {vgg_eval['macro_f1']:.3f} |",
        "",
    ]
    if blank_agent:
        lines.append(
            f"> Note: {blank_agent} agent response(s) did not match a known class and are "
            f"counted as wrong (blank prediction).\n"
        )
    lines += [
        "## Confusion matrices\n",
        f"![Confusion matrices]({png_path.name})\n",
        "## Per-class report — Agent (Claude API)\n",
        "```", agent_eval["report"], "```\n",
        "## Per-class report — VGG-16 (fine-tuned)\n",
        "```", vgg_eval["report"], "```\n",
        "## Disagreements to spot-check\n",
        "Images where the two branches predicted different classes "
        "(open a few by eye to judge which answer is more reasonable):\n",
    ]
    disagree = merged[
        merged["predicted_label_agent"] != merged["predicted_label_vgg"]
    ][["key", "true_label_agent", "predicted_label_agent", "predicted_label_vgg"]].head(15)
    if len(disagree):
        lines += [
            "| image | true | agent | vgg-16 |",
            "|---|---|---|---|",
        ]
        for _, r in disagree.iterrows():
            lines.append(
                f"| {r['key']} | {r['true_label_agent']} | "
                f"{r['predicted_label_agent'] or '(blank)'} | {r['predicted_label_vgg']} |"
            )
    else:
        lines.append("_No disagreements — the two branches predicted identically on every image._")
    lines.append("")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
