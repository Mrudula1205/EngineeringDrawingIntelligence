from __future__ import annotations

import io
import logging
import re
from typing import Dict, List, Tuple

import pandas as pd
import pytesseract
from PIL import Image

from pipeline.state import PipelineState

logger = logging.getLogger(__name__)


NOTES_REGEX = re.compile(r"\bnotes\b", re.IGNORECASE)
BULLET_REGEX = re.compile(r"^\s*(\d+)[\.\)]\s*(.+)$")
MATERIAL_REGEX = re.compile(r"\b(?:material|mat['\.]?l)[\s:]*([^\n]*)", re.IGNORECASE)


def _extract_from_raw_text_blocks(
    raw_text_blocks: List[dict],
) -> Tuple[Dict, Dict, Dict]:
    """
    Extract title, BOM, and notes from raw_text_blocks.
    Returns (title_result, notes_result, bom_result).
    """
    title_result = {}
    notes_result = {
        "material": None,
        "material_standard": None,
        "dimensional_notes": [],
        "surface_finish_notes": [],
        "process_notes": [],
        "general_notes": [],
        "raw_text": "",
    }
    bom_result = {"rows": []}

    if not raw_text_blocks:
        return title_result, notes_result, bom_result

    # Extract notes from raw_text_blocks
    notes_text = []
    for block in raw_text_blocks:
        text = block.get("text", "").strip()
        if NOTES_REGEX.search(text):
            notes_text.append(text)

    if notes_text:
        full_notes = "\n".join(notes_text)
        notes_result["raw_text"] = full_notes

        # Extract material
        material_match = MATERIAL_REGEX.search(full_notes)
        if material_match:
            notes_result["material"] = material_match.group(1).strip()

        # Parse bullet points
        bullets = []
        current_num = None
        current_text = ""

        for line in full_notes.split("\n"):
            line = re.sub(r"\s+", " ", line).strip()
            if not line:
                continue

            m = BULLET_REGEX.match(line)
            if m:
                if current_num is not None:
                    bullets.append((current_num, current_text.strip()))
                current_num = int(m.group(1))
                current_text = m.group(2)
            else:
                if current_num is not None:
                    current_text = f"{current_text} {line}".strip()

        if current_num is not None:
            bullets.append((current_num, current_text.strip()))

        # Categorize bullets
        for num, text in bullets:
            text_lower = text.lower()
            if any(kw in text_lower for kw in ["dimension", "tolerance", "surface"]):
                notes_result["dimensional_notes"].append(text)
            elif any(kw in text_lower for kw in ["finish", "coat", "plate"]):
                notes_result["surface_finish_notes"].append(text)
            elif any(kw in text_lower for kw in ["heat", "treat", "harden", "anneal"]):
                notes_result["process_notes"].append(text)
            else:
                notes_result["general_notes"].append(text)

    return title_result, notes_result, bom_result


def _extract_via_ocr(page_image_bytes: bytes) -> Tuple[Dict, Dict]:
    """
    Extract title block and BOM table via OCR.
    Returns (title_result, bom_result).
    """
    title_result = {}
    bom_result = {"rows": []}

    try:
        img = Image.open(io.BytesIO(page_image_bytes)).convert("RGB")
        w, h = img.size

        # Run Tesseract
        data = pytesseract.image_to_data(img, config="--psm 3", output_type=pytesseract.Output.DICT)
        df = pd.DataFrame(data)

        # Filter for bottom-right quadrant (title block)
        df_br = df[
            (df["left"] > 0.55 * w)
            & (df["top"] > 0.45 * h)
            & (df["text"].str.strip() != "")
            & (df["conf"] > 0)
        ].copy()

        if not df_br.empty:
            df_br["text_lower"] = df_br["text"].astype(str).str.lower()
            keywords = ["title", "dwg", "rev", "sheet", "scale", "weight", "size", "no.", "projection"]
            pattern = "|".join(keywords)
            anchors = df_br[df_br["text_lower"].str.contains(pattern, na=False)]

            if not anchors.empty:
                title_result["extraction_source"] = "ocr"
                title_result["detected_keywords"] = list(anchors["text"].unique())

        # BOM detection (left side with BOM keywords)
        df_clean = df[(df["text"].str.strip() != "") & (df["conf"] > 30)].copy()
        if not df_clean.empty:
            df_clean["text_lower"] = df_clean["text"].astype(str).str.lower()
            bom_keywords = ["bom", "bill of material", "qty", "quantity", "part"]
            bom_pattern = "|".join(bom_keywords)
            bom_anchors = df_clean[df_clean["text_lower"].str.contains(bom_pattern, na=False)]

            if not bom_anchors.empty:
                bom_result["extraction_source"] = "ocr"
                bom_result["detected_keywords"] = list(bom_anchors["text"].unique())

    except Exception as exc:
        print(f"Warning: OCR extraction failed: {exc}")

    return title_result, bom_result


async def extract_structured_data(state: PipelineState) -> dict:
    """
    Extract title block, BOM table, and notes from raw_text_blocks.
    Falls back to OCR if raw_text_blocks is empty.
    """
    job_id = state.get("job_id", "unknown")
    logger.info("📋 Extracting structured data (title, BOM, notes)...")
    
    raw_text_blocks = state.get("raw_text_blocks") or []

    if raw_text_blocks:
        # Extract from raw_text_blocks
        logger.info("✓ Using raw_text_blocks from Document AI (%d blocks)", len(raw_text_blocks))
        title_result, notes_result, bom_result = _extract_from_raw_text_blocks(raw_text_blocks)
        title_result.setdefault("extraction_source", "raw_text_blocks")
        bom_result.setdefault("extraction_source", "raw_text_blocks")
        logger.info("✓ Title: %s | Notes: %d items | BOM: %d rows", 
                   title_result.get("title", "N/A")[:50], 
                   len(notes_result.get("general_notes", [])),
                   len(bom_result.get("rows", [])))
    else:
        # Fall back to OCR
        logger.warning("⚠️ No raw_text_blocks, falling back to OCR extraction")
        page_image_bytes = (state.get("page_images") or [None])[0]
        if not page_image_bytes:
            raise ValueError("page_images is required for OCR extraction.")

        title_result, bom_result = _extract_via_ocr(page_image_bytes)
        notes_result = {
            "material": None,
            "material_standard": None,
            "dimensional_notes": [],
            "surface_finish_notes": [],
            "process_notes": [],
            "general_notes": [],
            "raw_text": "",
            "extraction_error": "Notes not found (no raw_text_blocks)",
        }
        logger.info("✓ OCR extraction complete. Title keywords: %s", title_result.get("detected_keywords", []))

    return {
        "title_result": title_result,
        "notes_result": notes_result,
        "bom_result": bom_result,
    }
