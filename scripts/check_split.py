"""
Step 2 debug checkpoint (cross-platform).

Verifies the shared split is sound before spending API money or GPU time:
  - per-class train/test counts (balance)
  - no image (by base name) appears in both train and test (leak check)
  - flags unreadable / corrupt images via Pillow

Usage: python scripts/check_split.py
"""

from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPLITS = PROJECT_ROOT / "data" / "splits"
IMG_EXTS = {".jpg", ".jpeg", ".png"}


def imgs(d: Path):
    return [p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS]


def main() -> None:
    if not SPLITS.exists():
        raise SystemExit(f"No splits at {SPLITS} — run 01_prepare_dataset.py first.")

    print(f"{'class':<12}{'train':>8}{'test':>8}")
    print("-" * 28)
    train_total = test_total = 0
    for cls_dir in sorted((SPLITS / "train").iterdir()):
        if not cls_dir.is_dir():
            continue
        cls = cls_dir.name
        n_tr = len(imgs(SPLITS / "train" / cls))
        n_te = len(imgs(SPLITS / "test" / cls))
        train_total += n_tr
        test_total += n_te
        print(f"{cls:<12}{n_tr:>8}{n_te:>8}")
    print("-" * 28)
    print(f"{'TOTAL':<12}{train_total:>8}{test_total:>8}\n")

    # Leak check by base filename.
    train_names = {p.name for p in imgs(SPLITS / "train")}
    test_names = {p.name for p in imgs(SPLITS / "test")}
    overlap = train_names & test_names
    if overlap:
        print(f"[LEAK] {len(overlap)} filename(s) appear in BOTH train and test:")
        for n in list(overlap)[:10]:
            print(f"       {n}")
    else:
        print("[OK] No filename overlap between train and test.")

    # Corruption check.
    try:
        from PIL import Image
    except ImportError:
        print("[skip] Pillow not installed — skipping corruption check.")
        return

    bad = []
    for p in imgs(SPLITS):
        try:
            with Image.open(p) as im:
                im.verify()
        except Exception as e:  # noqa: BLE001
            bad.append((p, str(e)))
    if bad:
        print(f"\n[CORRUPT] {len(bad)} unreadable image(s):")
        for p, err in bad[:10]:
            print(f"       {p.name}: {err}")
    else:
        print("[OK] All images readable.")


if __name__ == "__main__":
    main()
