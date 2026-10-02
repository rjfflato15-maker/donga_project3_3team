"""Preflight / run / resume the sole v3 heldout prediction attempt."""
import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.evaluation_predictions import preflight, run_predictions


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=PROJECT / "eval/dataset")
    parser.add_argument("--release", type=Path, default=PROJECT / "docs/eval/test/preparation/release_lock.json")
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/eval/test/v3_predictions")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.preflight:
            _, _, _, report = preflight(PROJECT, args.dataset, args.release)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            receipt = run_predictions(PROJECT, args.dataset, args.output, args.release, resume=args.resume)
            print(json.dumps({key: receipt[key] for key in ("attempt_id", "document_count", "frozen_at", "labels_read")}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print("예측 중단: " + str(exc)[:100], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
