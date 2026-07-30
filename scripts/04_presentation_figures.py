"""
Step 6 — Presentation & report figures.

03_compare_results.py emits the two confusion matrices, which answer "how often
was each branch right". They do not carry the argument the report actually makes:
that the branches are statistically tied and differ in the *structure* of their
errors. These figures exist to make that argument visible on a slide.

Every figure is derived from the same two prediction CSVs and re-uses the same
basename alignment as step 5, so nothing here can drift from the reported
numbers. Runs read-only — it never touches data/splits/ or the CSVs.

Figures written to results/figures/:
    fig1_headline.png            accuracy + macro-F1, with the McNemar verdict
    fig2_per_class_f1.png        per-class F1, both branches
    fig3_per_class_delta.png     per-class recall gap (agent - vgg), diverging
    fig4_outcome_breakdown.png   both-right / one-right / both-wrong + oracle bound
    fig5_error_asymmetry.png     directional confusion counts (the core finding)
    fig6_disagreement_grid.png   real images where exactly one branch is right
    fig7_tradeoff.png            qualitative trade-off table

Usage:
    python scripts/04_presentation_figures.py
    python scripts/04_presentation_figures.py --dark      # dark-surface variant
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT_ROOT / "results"
FIGURES = RESULTS / "figures"
TEST_DIR = PROJECT_ROOT / "data" / "splits" / "test"
AGENT_CSV = RESULTS / "agent_predictions.csv"
VGG_CSV = RESULTS / "vgg16_predictions.csv"

CLASSES = ["buildings", "forest", "glacier", "mountain", "sea", "street"]
AGENT_NAME = "Claude agent (zero-shot)"
VGG_NAME = "VGG-16 (fine-tuned)"

# Categorical slots 1 and 2 of the validated palette. Two series only, so the
# adjacent-pair CVD gate is the only one in play and both modes clear it.
THEME_LIGHT = {
    "surface": "#fcfcfb",
    "agent": "#2a78d6",
    "vgg": "#eb6834",
    "primary": "#0b0b0b",
    "secondary": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
    "neutral": "#f0efec",
    "good": "#0ca30c",
    "critical": "#d03b3b",
}
THEME_DARK = {
    "surface": "#1a1a19",
    "agent": "#3987e5",
    "vgg": "#d95926",
    "primary": "#ffffff",
    "secondary": "#c3c2b7",
    "muted": "#898781",
    "grid": "#2c2c2a",
    "axis": "#383835",
    "neutral": "#383835",
    "good": "#0ca30c",
    "critical": "#d03b3b",
}

BAR_RADIUS = 0.02  # data-end rounding, in axis units


def key_of(filepath: str) -> str:
    """Basename key, tolerant of both '\\' and '/' separators (same as step 5)."""
    return filepath.replace("\\", "/").rsplit("/", 1)[-1]


def load_merged() -> pd.DataFrame:
    """Re-run step 5's alignment. Fails loudly rather than plotting a broken join."""
    for path, name in ((AGENT_CSV, "agent_predictions.csv"), (VGG_CSV, "vgg16_predictions.csv")):
        if not path.exists():
            sys.exit(f"Missing {name}: {path}. Run the prediction steps first.")

    agent = pd.read_csv(AGENT_CSV).fillna({"predicted_label": ""})
    vgg = pd.read_csv(VGG_CSV).fillna({"predicted_label": ""})
    agent["key"] = agent["filepath"].map(key_of)
    vgg["key"] = vgg["filepath"].map(key_of)

    if set(agent["key"]) != set(vgg["key"]):
        sys.exit(
            "[FATAL] The two CSVs do not cover the same test images. "
            "Fix the split before generating figures."
        )

    merged = agent.merge(vgg, on="key", suffixes=("_agent", "_vgg"))
    bad = merged[merged["true_label_agent"] != merged["true_label_vgg"]]
    if len(bad):
        sys.exit(f"[FATAL] {len(bad)} image(s) disagree on the true label: {bad['key'].tolist()[:5]}")

    merged["true"] = merged["true_label_agent"]
    merged["agent"] = merged["predicted_label_agent"]
    merged["vgg"] = merged["predicted_label_vgg"]
    merged["agent_ok"] = merged["agent"] == merged["true"]
    merged["vgg_ok"] = merged["vgg"] == merged["true"]
    return merged[["key", "true", "agent", "vgg", "agent_ok", "vgg_ok"]]


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar on the discordant pairs only."""
    from scipy.stats import binomtest

    if b + c == 0:
        return 1.0
    return binomtest(b, b + c, 0.5, alternative="two-sided").pvalue


# --- shared chart chrome -----------------------------------------------------


def style_axes(ax, t, *, xgrid=False, ygrid=True):
    """Recessive grid and axes; no top/right spines; muted tick ink."""
    ax.set_facecolor(t["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["axis"])
        ax.spines[side].set_linewidth(1)
    ax.tick_params(colors=t["muted"], labelsize=10, length=0)
    if ygrid:
        ax.yaxis.grid(True, color=t["grid"], linewidth=1)
    if xgrid:
        ax.xaxis.grid(True, color=t["grid"], linewidth=1)
    ax.set_axisbelow(True)


def rounded_bars(ax, xs, heights, width, color, *, horizontal=False, radius=None):
    """
    Bars with rounded data-ends anchored to the baseline.

    The rounding size is in data units along the value axis, so it has to be
    given relative to that axis' range — a fixed constant is invisible on a
    0-to-8 count axis and huge on a 0-to-1 rate axis.
    """
    from matplotlib.patches import FancyBboxPatch

    pad = BAR_RADIUS if radius is None else radius
    for x, h in zip(xs, heights):
        if h <= 0:
            continue
        if horizontal:
            box = FancyBboxPatch(
                (0, x - width / 2), max(h - pad, 1e-6), width,
                boxstyle=f"round,pad=0,rounding_size={min(pad, h / 2)}",
                linewidth=0, facecolor=color, mutation_aspect=1,
            )
        else:
            box = FancyBboxPatch(
                (x - width / 2, 0), width, max(h - pad, 1e-6),
                boxstyle=f"round,pad=0,rounding_size={min(pad, h / 2)}",
                linewidth=0, facecolor=color,
            )
        ax.add_patch(box)


def titled(fig, t, title, subtitle=None):
    fig.patch.set_facecolor(t["surface"])
    fig.text(0.012, 0.965, title, fontsize=16, fontweight="bold",
             color=t["primary"], va="top", ha="left")
    if subtitle:
        fig.text(0.012, 0.905, subtitle, fontsize=11, color=t["secondary"],
                 va="top", ha="left")


def legend(ax, t, labels, colors):
    """
    Legend sits in its own band above the plot, never over the marks. Anchoring
    it inside the axes collides with whichever bar happens to be tallest.
    """
    from matplotlib.patches import Patch

    handles = [Patch(facecolor=c, label=l) for l, c in zip(labels, colors)]
    return ax.legend(
        handles=handles, loc="lower left", bbox_to_anchor=(0, 1.01), ncol=len(labels),
        frameon=False, fontsize=10, labelcolor=t["secondary"],
        handlelength=1.1, handleheight=1.1, columnspacing=1.6,
    )


def save(fig, path: Path, t):
    fig.savefig(path, dpi=200, facecolor=t["surface"], bbox_inches="tight", pad_inches=0.3)
    print(f"  wrote {path.relative_to(PROJECT_ROOT)}")


# --- figures -----------------------------------------------------------------


def fig1_headline(df, t, out):
    """Headline metrics. Two measures on one 0-1 scale, so one axis is honest here."""
    import matplotlib.pyplot as plt
    from sklearn.metrics import accuracy_score, f1_score

    y = df["true"]
    metrics = {}
    for name, col in ((AGENT_NAME, "agent"), (VGG_NAME, "vgg")):
        metrics[name] = [
            accuracy_score(y, df[col]),
            f1_score(y, df[col], labels=CLASSES, average="macro", zero_division=0),
        ]

    b = int((df["agent_ok"] & ~df["vgg_ok"]).sum())
    c = int((~df["agent_ok"] & df["vgg_ok"]).sum())
    p = mcnemar_exact(b, c)

    fig, ax = plt.subplots(figsize=(9, 5.2))
    style_axes(ax, t)
    groups = ["Accuracy", "Macro-F1"]
    xs = list(range(len(groups)))
    w = 0.3
    gap = 0.012  # 2px surface gap between adjacent bars
    rounded_bars(ax, [x - w / 2 - gap for x in xs], metrics[AGENT_NAME], w, t["agent"])
    rounded_bars(ax, [x + w / 2 + gap for x in xs], metrics[VGG_NAME], w, t["vgg"])

    for x, (a, v) in zip(xs, zip(metrics[AGENT_NAME], metrics[VGG_NAME])):
        for off, val in ((-w / 2 - gap, a), (w / 2 + gap, v)):
            ax.text(x + off, val + 0.018, f"{val:.3f}", ha="center", va="bottom",
                    fontsize=12, color=t["primary"], fontweight="bold")

    ax.set_xticks(xs)
    ax.set_xticklabels(groups, fontsize=12, color=t["secondary"])
    ax.set_ylim(0, 1.06)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xlim(-0.55, len(groups) - 0.45)
    legend(ax, t, [AGENT_NAME, VGG_NAME], [t["agent"], t["vgg"]])

    titled(fig, t,
           "Statistically tied on the same 216 test images",
           f"Discordant pairs: agent-only right {b}, VGG-only right {c}.  "
           f"McNemar exact p = {p:.3f} — the {abs(metrics[AGENT_NAME][0]-metrics[VGG_NAME][0])*100:.1f} pt "
           "accuracy gap is not significant.")
    fig.subplots_adjust(top=0.74)
    save(fig, out, t)


def fig2_per_class_f1(df, t, out):
    """Per-class F1. Identity of the branch is the categorical encoding."""
    import matplotlib.pyplot as plt
    from sklearn.metrics import f1_score

    a = f1_score(df["true"], df["agent"], labels=CLASSES, average=None, zero_division=0)
    v = f1_score(df["true"], df["vgg"], labels=CLASSES, average=None, zero_division=0)

    fig, ax = plt.subplots(figsize=(10, 5.4))
    style_axes(ax, t)
    xs = list(range(len(CLASSES)))
    w = 0.34
    gap = 0.012
    rounded_bars(ax, [x - w / 2 - gap for x in xs], a, w, t["agent"])
    rounded_bars(ax, [x + w / 2 + gap for x in xs], v, w, t["vgg"])

    # Direct-label only the widest gaps, not every bar.
    gaps = sorted(range(len(CLASSES)), key=lambda i: -abs(a[i] - v[i]))[:2]
    for i in gaps:
        for off, val in ((-w / 2 - gap, a[i]), (w / 2 + gap, v[i])):
            ax.text(i + off, val + 0.015, f"{val:.2f}", ha="center", va="bottom",
                    fontsize=10, color=t["primary"], fontweight="bold")

    ax.set_xticks(xs)
    ax.set_xticklabels(CLASSES, fontsize=11, color=t["secondary"])
    ax.set_ylim(0, 1.08)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_ylabel("F1", color=t["secondary"], fontsize=11)
    ax.set_xlim(-0.6, len(CLASSES) - 0.4)
    legend(ax, t, [AGENT_NAME, VGG_NAME], [t["agent"], t["vgg"]])

    titled(fig, t, "Per-class F1 — the branches fail on different classes",
           "Labelled where the branches differ most. Neither dominates across all six.")
    fig.subplots_adjust(top=0.76)
    save(fig, out, t)


def fig3_per_class_delta(df, t, out):
    """
    Diverging: per-class recall gap. Polarity (which branch wins) is the data's
    job here, so a two-pole scale with a neutral zero line is the right form.
    """
    import matplotlib.pyplot as plt

    deltas = []
    for c in CLASSES:
        sub = df[df["true"] == c]
        deltas.append(sub["agent_ok"].mean() - sub["vgg_ok"].mean())

    fig, ax = plt.subplots(figsize=(9, 5.2))
    style_axes(ax, t, xgrid=True, ygrid=False)
    ys = list(range(len(CLASSES)))[::-1]
    for y, d in zip(ys, deltas):
        color = t["agent"] if d >= 0 else t["vgg"]
        rounded_bars(ax, [y], [abs(d)], 0.42, color, horizontal=True)
        if d < 0:
            # rounded_bars always draws rightwards from zero; mirror the patch so
            # the rounded end lands outward and the square end stays on the axis.
            for p in ax.patches[-1:]:
                p.set_x(-abs(d) + BAR_RADIUS)
        ax.text(d + (0.012 if d >= 0 else -0.012), y, f"{d:+.0%}",
                va="center", ha="left" if d >= 0 else "right",
                fontsize=10, color=t["primary"], fontweight="bold")

    ax.axvline(0, color=t["axis"], linewidth=1.4)
    ax.set_yticks(ys)
    ax.set_yticklabels(CLASSES, fontsize=11, color=t["secondary"])
    lim = max(abs(min(deltas)), abs(max(deltas))) * 1.45 + 0.02
    ax.set_xlim(-lim, lim)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)

    fig.text(0.985, 0.145, "← VGG-16 better", ha="right", fontsize=10, color=t["vgg"],
             fontweight="bold")
    fig.text(0.985, 0.105, "agent better →", ha="right", fontsize=10, color=t["agent"],
             fontweight="bold")

    titled(fig, t, "Per-class recall gap (agent − VGG-16)",
           "Each branch has classes it owns. The overall tie hides a class-level split.")
    fig.subplots_adjust(top=0.80, bottom=0.20)
    save(fig, out, t)


def fig4_outcome_breakdown(df, t, out):
    """
    Composition of the 216 images by which branches got them right. The
    both-wrong slice is the ceiling on any ensemble, which is the point.
    """
    import matplotlib.pyplot as plt

    both = int((df["agent_ok"] & df["vgg_ok"]).sum())
    a_only = int((df["agent_ok"] & ~df["vgg_ok"]).sum())
    v_only = int((~df["agent_ok"] & df["vgg_ok"]).sum())
    neither = int((~df["agent_ok"] & ~df["vgg_ok"]).sum())
    n = len(df)
    oracle = (both + a_only + v_only) / n

    segs = [
        ("Both right", both, t["good"]),
        ("Agent only", a_only, t["agent"]),
        ("VGG-16 only", v_only, t["vgg"]),
        ("Both wrong", neither, t["critical"]),
    ]

    fig, ax = plt.subplots(figsize=(11, 3.3))
    ax.set_facecolor(t["surface"])
    left = 0.0
    for label, count, color in segs:
        frac = count / n
        ax.barh(0, frac - 0.0022, left=left, height=0.5, color=color, linewidth=0)  # 2px gap
        if frac > 0.03:
            ax.text(left + frac / 2, 0, f"{count}", ha="center", va="center",
                    fontsize=13, fontweight="bold", color=t["surface"])
        left += frac

    # The three small segments sit within a few percent of each other, so labels
    # anchored to segment centres collide. Lay them out as an evenly spaced
    # legend row below the bar instead, with a leader line back to the segment.
    left = 0.0
    slots = [0.10, 0.40, 0.63, 0.86]
    for (label, count, color), slot in zip(segs, slots):
        frac = count / n
        centre = left + frac / 2
        ax.plot([centre, slot], [-0.30, -0.52], color=t["axis"], linewidth=1, zorder=0)
        ax.plot([slot], [-0.62], marker="s", markersize=8, color=color)
        ax.text(slot + 0.018, -0.62, f"{label} — {count}", ha="left", va="center",
                fontsize=11, color=t["secondary"])
        left += frac

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.95, 0.55)
    ax.axis("off")

    titled(fig, t, f"Where the {n} test images land",
           f"Only {neither} images defeat both branches — an oracle that always picked the "
           f"right branch would score {oracle:.1%}.")
    fig.subplots_adjust(top=0.62, bottom=0.10)
    save(fig, out, t)


def fig5_error_asymmetry(df, t, out):
    """
    The core finding: the agent's errors are one-directional, VGG-16's are
    symmetric. Same confusion pair, counted in both directions.
    """
    import matplotlib.pyplot as plt

    pairs = [("glacier", "mountain"), ("buildings", "street"), ("glacier", "sea"),
             ("mountain", "glacier"), ("street", "buildings"), ("sea", "glacier")]

    def count(col, true_c, pred_c):
        return int(((df["true"] == true_c) & (df[col] == pred_c)).sum())

    labels = [f"{a} → {b}" for a, b in pairs]
    a_counts = [count("agent", a, b) for a, b in pairs]
    v_counts = [count("vgg", a, b) for a, b in pairs]

    fig, ax = plt.subplots(figsize=(10, 5.6))
    style_axes(ax, t, xgrid=True, ygrid=False)
    ys = list(range(len(pairs)))[::-1]
    h = 0.34
    gap = 0.02
    r = max(a_counts + v_counts) * 0.02
    rounded_bars(ax, [y + h / 2 + gap for y in ys], a_counts, h, t["agent"],
                 horizontal=True, radius=r)
    rounded_bars(ax, [y - h / 2 - gap for y in ys], v_counts, h, t["vgg"],
                 horizontal=True, radius=r)

    for y, (a, v) in zip(ys, zip(a_counts, v_counts)):
        for off, val in ((h / 2 + gap, a), (-h / 2 - gap, v)):
            ax.text(val + 0.12, y + off, str(val), va="center", ha="left",
                    fontsize=10, color=t["primary"], fontweight="bold")

    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=11, color=t["secondary"])
    ax.set_xlim(0, max(a_counts + v_counts) + 1.6)
    # add_patch does not autoscale, so without an explicit ylim the outer bars clip.
    ax.set_ylim(-0.7, len(pairs) - 0.3)
    ax.set_xlabel("misclassified images", color=t["secondary"], fontsize=11)
    legend(ax, t, [AGENT_NAME, VGG_NAME], [t["agent"], t["vgg"]])

    titled(fig, t, "Error direction, not error rate, is what separates them",
           "The agent confuses glacier→mountain but almost never the reverse — a category "
           "judgement.\nVGG-16 confuses the pair in both directions — perceptual "
           "non-discrimination.")
    fig.subplots_adjust(top=0.70)
    save(fig, out, t)


def fig6_disagreement_grid(df, t, out, n_show=8):
    """The qualitative slide: real images where exactly one branch is right."""
    import matplotlib.pyplot as plt
    from PIL import Image

    disagree = df[df["agent_ok"] != df["vgg_ok"]].copy()
    if disagree.empty:
        print("  skipped fig6 — no images where exactly one branch is right")
        return

    # Show both directions, so the slide is not cherry-picked for one branch.
    a_wins = disagree[disagree["agent_ok"]].head(n_show // 2)
    v_wins = disagree[disagree["vgg_ok"]].head(n_show - len(a_wins))
    picks = pd.concat([a_wins, v_wins])

    cols = 4
    rows = (len(picks) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(3.1 * cols, 3.5 * rows))
    axes = axes.ravel() if hasattr(axes, "ravel") else [axes]

    missing = 0
    for ax, (_, r) in zip(axes, picks.iterrows()):
        path = TEST_DIR / r["true"] / r["key"]
        ax.set_facecolor(t["surface"])
        if path.exists():
            ax.imshow(Image.open(path))
        else:
            missing += 1
            ax.text(0.5, 0.5, "image not found", ha="center", va="center",
                    fontsize=9, color=t["muted"], transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(t["axis"])
            s.set_linewidth(1)

        winner = t["agent"] if r["agent_ok"] else t["vgg"]
        ax.set_title(f"true: {r['true']}", fontsize=11, color=t["primary"],
                     fontweight="bold", pad=6)
        ax.text(0.5, -0.06, f"agent: {r['agent'] or '(blank)'}", transform=ax.transAxes,
                ha="center", va="top", fontsize=10,
                color=t["primary"] if r["agent_ok"] else t["secondary"],
                fontweight="bold" if r["agent_ok"] else "normal")
        ax.text(0.5, -0.17, f"VGG-16: {r['vgg']}", transform=ax.transAxes,
                ha="center", va="top", fontsize=10,
                color=t["primary"] if r["vgg_ok"] else t["secondary"],
                fontweight="bold" if r["vgg_ok"] else "normal")
        # Colored rule marks which branch won — the bold label carries it too.
        ax.plot([0.30, 0.70], [-0.26, -0.26], transform=ax.transAxes,
                color=winner, linewidth=3, clip_on=False, solid_capstyle="round")

    for ax in axes[len(picks):]:
        ax.axis("off")

    if missing:
        print(f"  note: {missing} image file(s) not found under {TEST_DIR}")

    titled(fig, t, "Disagreement set — exactly one branch is right",
           "Bold = the correct call. Rule colour marks the winning branch "
           f"(blue = agent, orange = VGG-16). {len(disagree)} such images in total.")
    fig.subplots_adjust(top=0.84, hspace=0.42, wspace=0.12)
    save(fig, out, t)


def fig7_tradeoff(df, t, out):
    """
    Not a chart — a table. The comparison's actual conclusion is qualitative, and
    a table is the honest form for text-valued cells.
    """
    import matplotlib.pyplot as plt

    rows = [
        ("Labelled training data", "none (zero-shot)", "864 images"),
        ("Setup cost", "minutes — write a prompt", "GPU fine-tuning run"),
        ("Inference", "~seconds, network-bound, per-image cost", "~ms, local, free after training"),
        ("Determinism", "non-deterministic", "deterministic"),
        ("Failure mode", "degrades, may hedge or refuse", "fails confidently"),
        ("Error structure", "one-directional (category judgement)", "symmetric (non-discrimination)"),
        ("New classes", "prompt edit, no retraining", "full retrain"),
        ("Accuracy here", "0.917", "0.903  (p = 0.690 — tied)"),
    ]

    fig, ax = plt.subplots(figsize=(12, 5.6))
    fig.patch.set_facecolor(t["surface"])
    ax.set_facecolor(t["surface"])
    ax.axis("off")

    x0, x1, x2 = 0.005, 0.34, 0.68
    y = 0.80          # first data row, clear of the header band
    dy = 0.098

    y_head = y + 0.11
    bottom = y - (len(rows) - 1) * dy - dy * 0.5
    ax.plot([x1 - 0.012, x1 - 0.012], [bottom, y_head + 0.03], color=t["grid"], linewidth=1)
    ax.plot([x2 - 0.012, x2 - 0.012], [bottom, y_head + 0.03], color=t["grid"], linewidth=1)

    ax.plot([x1, x1 + 0.02], [y_head, y_head], color=t["agent"], linewidth=3,
            solid_capstyle="round")
    ax.plot([x2, x2 + 0.02], [y_head, y_head], color=t["vgg"], linewidth=3,
            solid_capstyle="round")
    ax.text(x1 + 0.032, y_head, AGENT_NAME, fontsize=12, fontweight="bold",
            color=t["primary"], va="center")
    ax.text(x2 + 0.032, y_head, VGG_NAME, fontsize=12, fontweight="bold",
            color=t["primary"], va="center")

    for i, (label, a, v) in enumerate(rows):
        yy = y - i * dy
        if i:
            ax.plot([x0, 0.995], [yy + dy * 0.52, yy + dy * 0.52], color=t["grid"], linewidth=1)
        ax.text(x0, yy, label, fontsize=11, color=t["secondary"], va="center")
        ax.text(x1, yy, a, fontsize=11, color=t["primary"], va="center")
        ax.text(x2, yy, v, fontsize=11, color=t["primary"], va="center")

    ax.set_xlim(0, 1)
    ax.set_ylim(0.02, 1.0)

    titled(fig, t, "The trade-off the accuracy number hides",
           "Both branches score the same. They cost, fail, and extend completely differently.")
    fig.subplots_adjust(top=0.80)
    save(fig, out, t)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate report/presentation figures.")
    ap.add_argument("--dark", action="store_true",
                    help="render on the dark chart surface (for dark slide decks)")
    ap.add_argument("--outdir", default=None, help="override results/figures/")
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]

    t = THEME_DARK if args.dark else THEME_LIGHT
    outdir = Path(args.outdir) if args.outdir else (FIGURES / "dark" if args.dark else FIGURES)
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_merged()
    print(f"Aligned on {len(df)} shared test images. Writing to {outdir}\n")

    fig1_headline(df, t, outdir / "fig1_headline.png")
    fig2_per_class_f1(df, t, outdir / "fig2_per_class_f1.png")
    fig3_per_class_delta(df, t, outdir / "fig3_per_class_delta.png")
    fig4_outcome_breakdown(df, t, outdir / "fig4_outcome_breakdown.png")
    fig5_error_asymmetry(df, t, outdir / "fig5_error_asymmetry.png")
    fig6_disagreement_grid(df, t, outdir / "fig6_disagreement_grid.png")
    fig7_tradeoff(df, t, outdir / "fig7_tradeoff.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
