"""Check readiness or preserve the single locked v4 test2 prediction attempt."""
import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.test2_predictions import preflight, run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="No extraction or heldout original reads")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dataset", type=Path, default=PROJECT / "eval/dataset-v2")
    parser.add_argument("--release", type=Path, default=PROJECT / "docs/eval/test2/preparation/release_lock.json")
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/eval/test2/v4_predictions")
    args = parser.parse_args(argv)
    try:
        if args.check and args.resume:
            raise ValueError("CHECK_AND_RESUME_ARE_EXCLUSIVE")
        if args.check:
            report = preflight(PROJECT, args.dataset, args.release, check_only=True)[3]
        else:
            receipt = run(PROJECT, args.dataset, args.output, args.release, resume=args.resume)
            report = {key: receipt[key] for key in ("attempt_id", "document_count", "frozen_at", "labels_read", "guard_policy", "release_version")}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print("test2 예측 중단: " + str(exc)[:160], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
