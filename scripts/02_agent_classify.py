"""
Step 3 — Agent classification via the Claude API vision model.

Sends every image in data/splits/test/ to Claude, asks it to classify into one of
the fixed Intel class labels, and logs predictions incrementally to
results/agent_predictions.csv.

Design notes:
  - Model is claude-haiku-4-5 — cheapest/fastest, appropriate for one-word
    classification. (Confirmed current model ID; the dated -20251001 suffix is not needed.)
  - The Anthropic SDK auto-retries 429 / 5xx with exponential backoff; we set
    max_retries=5. Rate-limit friendliness: a small sleep between calls.
  - Writes each row immediately (not at the end) so a crash loses nothing, and
    skips images already present in the CSV so a restart never re-bills them.
  - Predictions are normalized to the known class set; anything unrecognized is
    kept verbatim in raw_response and flagged so Step 5 can decide how to score it.

Usage:
    python scripts/02_agent_classify.py --limit 10     # smoke test first
    python scripts/02_agent_classify.py                # full run (resumes)

Requires ANTHROPIC_API_KEY in .env (never hardcode it).
"""

import argparse
import base64
import csv
import sys
import time
from pathlib import Path

CLASSES = ["buildings", "forest", "glacier", "mountain", "sea", "street"]
IMG_EXTS = {".jpg", ".jpeg", ".png"}
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

MODEL = "claude-haiku-4-5"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = PROJECT_ROOT / "data" / "splits" / "test"
OUT_CSV = PROJECT_ROOT / "results" / "agent_predictions.csv"

CSV_FIELDS = ["filepath", "true_label", "predicted_label", "raw_response"]

# Tight prompt — the single most common bug here is the model adding extra words
# ("I think it's a forest."). Force a bare label from the known set.
PROMPT = (
    "Classify this image into exactly one of these scene categories.\n"
    "Reply with ONLY one of these exact lowercase words, nothing else:\n"
    f"{', '.join(CLASSES)}"
)


def load_api_key() -> None:
    """Load ANTHROPIC_API_KEY from .env into the environment."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        sys.exit("python-dotenv not installed. Run: pip install -r requirements.txt")
    load_dotenv(PROJECT_ROOT / ".env")
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env and paste your key:\n"
            "  cp .env.example .env"
        )


def collect_test_images() -> list[tuple[Path, str]]:
    """Return (path, true_label) for every test image, sorted for determinism."""
    if not TEST_DIR.exists():
        sys.exit(f"No test split at {TEST_DIR} — run 01_prepare_dataset.py first.")
    items: list[tuple[Path, str]] = []
    for cls_dir in sorted(TEST_DIR.iterdir()):
        if not cls_dir.is_dir():
            continue
        for p in sorted(cls_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in IMG_EXTS:
                items.append((p, cls_dir.name))
    return items


def already_done() -> set[str]:
    """Filepaths already recorded in the CSV — so a restart skips them."""
    if not OUT_CSV.exists():
        return set()
    done: set[str] = set()
    with OUT_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            done.add(row["filepath"])
    return done


def normalize(raw: str) -> str:
    """Map the model's reply to a known class, or '' if unrecognized."""
    text = raw.strip().lower()
    if text in CLASSES:
        return text
    # Tolerate stray punctuation / extra words: pick the first class name that appears.
    for cls in CLASSES:
        if cls in text:
            return cls
    return ""


def classify_image(client, path: Path) -> str:
    """One API call → the model's raw text response."""
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    media_type = MEDIA_TYPES[path.suffix.lower()]
    response = client.messages.create(
        model=MODEL,
        max_tokens=16,  # one word is plenty
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": media_type, "data": data,
                }},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    return next((b.text for b in response.content if b.type == "text"), "").strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Classify test images with the Claude API.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only classify the first N not-yet-done images (smoke test).")
    ap.add_argument("--delay", type=float, default=0.3,
                    help="Seconds to sleep between calls (default: 0.3).")
    args = ap.parse_args()

    load_api_key()
    import anthropic

    client = anthropic.Anthropic(max_retries=5)  # SDK handles 429/5xx backoff

    images = collect_test_images()
    done = already_done()
    pending = [(p, lbl) for p, lbl in images if str(p) not in done]
    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"Total test images: {len(images)} | already done: {len(done)} | "
          f"processing now: {len(pending)}")
    if not pending:
        print("Nothing to do. (Delete results/agent_predictions.csv to re-run from scratch.)")
        return

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_header = not OUT_CSV.exists()
    unknown = 0

    with OUT_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()

        for i, (path, true_label) in enumerate(pending, start=1):
            try:
                raw = classify_image(client, path)
            except anthropic.APIError as e:  # noqa: BLE001 — log and keep going
                print(f"  [ERROR] {path.name}: {e}. Skipping (rerun to retry).")
                continue

            pred = normalize(raw)
            if not pred:
                unknown += 1
            writer.writerow({
                "filepath": str(path),
                "true_label": true_label,
                "predicted_label": pred,      # '' if unrecognized
                "raw_response": raw,
            })
            f.flush()  # persist immediately — crash-safe

            if i % 20 == 0 or i == len(pending):
                print(f"  Processed {i}/{len(pending)}...")
            time.sleep(args.delay)

    print(f"\nDone. Wrote to {OUT_CSV}")
    if unknown:
        print(f"[warn] {unknown} response(s) did not match a known class "
              f"(predicted_label left blank). Inspect raw_response and tighten the prompt "
              f"if this is more than a couple.")


if __name__ == "__main__":
    main()
