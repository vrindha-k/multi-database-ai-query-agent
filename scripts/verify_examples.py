"""Execute every documented example and save results calculated by PostgreSQL."""

import json
from pathlib import Path

from app.config import get_settings
from app.database import Registry


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    (root / "docs").mkdir(exist_ok=True)
    examples = json.loads((root / "examples/questions.json").read_text())
    registry = Registry(get_settings())
    lines = [
        "# Verified synthetic-data examples",
        "",
        "These results are calculated by PostgreSQL using `scripts/verify_examples.py`.",
        "Dates are fixed in 2025. Revenue is order-item gross revenue for completed orders.",
        "The SQL below is a reproducible reference, not a claim about a live Claude response.",
        "",
    ]
    try:
        for index, example in enumerate(examples, 1):
            result = registry.run_query(example["database_id"], example["sql"])
            example["expected"] = {"columns": result["columns"], "rows": result["rows"]}
            lines.extend(
                [
                    f"## {index}. {example['question']}",
                    "",
                    f"Database: `{example['database_id']}`",
                    "",
                    "```sql",
                    result["sql"],
                    "```",
                    "",
                    "```json",
                    json.dumps(example["expected"], indent=2),
                    "```",
                    "",
                ]
            )
        (root / "examples/verified.json").write_text(json.dumps(examples, indent=2) + "\n")
        (root / "docs/EXAMPLES.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"Verified {len(examples)} reference questions against PostgreSQL")
    finally:
        registry.close()


if __name__ == "__main__":
    main()
