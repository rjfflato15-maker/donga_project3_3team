"""Score immutable v3 predictions without running OCR, LLM or guards."""
import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.prediction_scoring import rescore
from backend.prediction_artifacts import write_json


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PROJECT / "docs/eval/test/v3_predictions")
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--preliminary", action="store_true")
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/eval/test/v3_scores")
    args = parser.parse_args(argv)
    try:
        report = rescore(args.package, args.labels, preliminary=args.preliminary)
        name = report["metadata"]["phase"] + "_" + report["metadata"]["labels_sha256"][:16] + ".json"
        destination = args.output / name
        if not destination.exists():
            write_json(destination, report, exclusive=True)
        elif json.loads(destination.read_text(encoding="utf-8")) != report:
            raise ValueError("EXISTING_SCORE_CHANGED")
        print(json.dumps({"path": str(destination), "phase": report["metadata"]["phase"],
                          "new_inference_calls": 0, "modes": {mode: {key: metrics[key] for key in
                          ("field_accuracy", "check_state_accuracy", "wrong_pass_counts", "mean_document_seconds")}
                          for mode, metrics in report["metrics"].items()}}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print("재채점 중단: " + str(exc)[:100], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
