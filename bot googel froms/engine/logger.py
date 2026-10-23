import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ResultLogger:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._json_path = self.output_dir / "results.json"
        self.records: list[dict[str, Any]] = []
        if self._json_path.exists():
            try:
                loaded = json.loads(self._json_path.read_text(encoding="utf-8"))
                if not isinstance(loaded, list) or any(
                    not isinstance(record, dict) for record in loaded
                ):
                    raise ValueError("Results log must contain a JSON array of objects.")
                self.records = loaded
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"Could not read existing results log: {exc}") from exc

    def add(self, record: dict[str, Any]) -> None:
        self.records.append(
            {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
        )
        self.export_json()

    def export_json(self, path: Path | None = None) -> Path:
        destination = path or self.output_dir / "results.json"
        destination.write_text(
            json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return destination

    def export_csv(self, path: Path | None = None) -> Path:
        import csv

        destination = path or self.output_dir / "results.csv"
        fields = [
            "timestamp",
            "scenario_id",
            "model",
            "question_count",
            "valid_count",
            "invalid_count",
            "browser_status",
            "submission_status",
            "browser_error",
            "duration_seconds",
            "status",
        ]
        with destination.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows({key: record.get(key, "") for key in fields} for record in self.records)
        return destination
