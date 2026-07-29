"""
Step 2 — Dataset preparation.

Downloads the Intel Image Classification dataset, subsamples a balanced set per
class, and creates a single shared 80/20 train/test split under data/splits/.

Both branches of the project are evaluated ONLY on data/splits/test/ — that shared
test set is what makes the agent-vs-VGG16 comparison fair. VGG-16 trains on
data/splits/train/; the agent ignores train/ entirely.

Usage:
    python scripts/01_prepare_dataset.py                 # default: 180 imgs/class, 80/20 split
    python scripts/01_prepare_dataset.py --per-class 150 --seed 42
    python scripts/01_prepare_dataset.py --raw-dir data/raw/seg_train  # skip download, use local

Requires Kaggle credentials for the download step (see --help / README). If you
already have the images locally, pass --raw-dir to skip the download.
"""

import argparse
import random
import shutil
import sys
from pathlib import Path

# Intel Image Classification canonical 6 classes.
CLASSES = ["buildings", "forest", "glacier", "mountain", "sea", "street"]
IMG_EXTS = {".jpg", ".jpeg", ".png"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPLITS_DIR = PROJECT_ROOT / "data" / "splits"


def find_class_dirs(root: Path) -> dict[str, Path]:
    """Locate a folder per class under `root`, searching recursively.

    The Intel dataset unzips to a nested layout (e.g. seg_train/seg_train/<class>/),
    so we search for the deepest directory matching each class name that actually
    contains images.
    """
    found: dict[str, Path] = {}
    for cls in CLASSES:
        candidates = [
            d for d in root.rglob(cls)
            if d.is_dir() and any(p.suffix.lower() in IMG_EXTS for p in d.iterdir() if p.is_file())
        ]
        if candidates:
            # Prefer the one with the most images.
            best = max(candidates, key=lambda d: sum(
                1 for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS
            ))
            found[cls] = best
    return found


def download_dataset() -> Path:
    """Download Intel Image Classification via kagglehub, return its local path."""
    try:
        import kagglehub
    except ImportError:
        sys.exit("kagglehub not installed. Run: pip install -r requirements.txt")

    print("Downloading Intel Image Classification via kagglehub ...")
    print("(Requires Kaggle credentials: place kaggle.json in ~/.kaggle/ or set")
    print(" KAGGLE_USERNAME / KAGGLE_KEY env vars. See https://www.kaggle.com/settings)")
    path = kagglehub.dataset_download("puneet6060/intel-image-classification")
    print(f"Downloaded to: {path}")
    return Path(path)


def list_images(class_dir: Path) -> list[Path]:
    return sorted(
        p for p in class_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMG_EXTS
    )


def prepare(raw_root: Path, per_class: int, test_frac: float, seed: int) -> None:
    rng = random.Random(seed)

    class_dirs = find_class_dirs(raw_root)
    missing = [c for c in CLASSES if c not in class_dirs]
    if missing:
        sys.exit(
            f"Could not find image folders for classes: {missing}\n"
            f"Searched under: {raw_root}\n"
            f"Pass --raw-dir pointing at a folder that contains one subfolder per class."
        )

    # Fresh splits every run so re-running is deterministic and leak-free.
    if SPLITS_DIR.exists():
        for sub in ("train", "test"):
            shutil.rmtree(SPLITS_DIR / sub, ignore_errors=True)
    for sub in ("train", "test"):
        for cls in CLASSES:
            (SPLITS_DIR / sub / cls).mkdir(parents=True, exist_ok=True)

    print(f"\n{'class':<12}{'available':>12}{'sampled':>10}{'train':>8}{'test':>8}")
    print("-" * 50)

    totals = {"train": 0, "test": 0}
    for cls in CLASSES:
        images = list_images(class_dirs[cls])
        available = len(images)
        rng.shuffle(images)
        sampled = images[: min(per_class, available)]

        n_test = max(1, round(len(sampled) * test_frac))
        test_imgs = sampled[:n_test]
        train_imgs = sampled[n_test:]

        # Prefix filenames with the class so names are globally unique across the
        # split — makes the train/test overlap check in the debug checkpoint reliable.
        for split_name, imgs in (("train", train_imgs), ("test", test_imgs)):
            for src in imgs:
                dst = SPLITS_DIR / split_name / cls / f"{cls}_{src.name}"
                shutil.copy2(src, dst)

        totals["train"] += len(train_imgs)
        totals["test"] += len(test_imgs)
        print(f"{cls:<12}{available:>12}{len(sampled):>10}{len(train_imgs):>8}{len(test_imgs):>8}")

    print("-" * 50)
    print(f"{'TOTAL':<12}{'':>12}{'':>10}{totals['train']:>8}{totals['test']:>8}")
    print(f"\nSplits written to: {SPLITS_DIR}")
    print("Next: verify balance with the Step 2 debug checkpoint, then run Step 3.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepare shared train/test split.")
    ap.add_argument("--per-class", type=int, default=180,
                    help="Images to sample per class before splitting (default: 180).")
    ap.add_argument("--test-frac", type=float, default=0.20,
                    help="Fraction of each class held out for the shared test set (default: 0.20).")
    ap.add_argument("--seed", type=int, default=42, help="Random seed (default: 42).")
    ap.add_argument("--raw-dir", type=str, default=None,
                    help="Local folder containing per-class subfolders. If omitted, "
                         "downloads from Kaggle via kagglehub.")
    args = ap.parse_args()

    raw_root = Path(args.raw_dir).resolve() if args.raw_dir else download_dataset()
    if not raw_root.exists():
        sys.exit(f"Path does not exist: {raw_root}")

    prepare(raw_root, args.per_class, args.test_frac, args.seed)


if __name__ == "__main__":
    main()
