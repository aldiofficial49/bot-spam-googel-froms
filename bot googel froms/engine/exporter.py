from pathlib import Path

from engine.logger import ResultLogger


def export_results(logger: ResultLogger, output_format: str, path: Path | None = None) -> Path:
    if output_format == "json":
        return logger.export_json(path)
    if output_format == "csv":
        return logger.export_csv(path)
    raise ValueError("Export format must be 'json' or 'csv'.")
