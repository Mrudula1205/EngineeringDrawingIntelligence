from __future__ import annotations

import json
from pathlib import Path

from utils.excel_utils import generate_excel_from_firestore


def main() -> None:
    sample_path = Path(__file__).parent / "sample_drawing.json"
    output_path = Path(__file__).parent / "sample_output.xlsx"

    drawing = json.loads(sample_path.read_text(encoding="utf-8"))
    excel_bytes = generate_excel_from_firestore([drawing])
    output_path.write_bytes(excel_bytes)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
