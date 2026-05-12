from __future__ import annotations

import io
import logging
import re
from typing import Dict, List, Tuple

import pandas as pd
import pytesseract
import cv2
import numpy as np
from PIL import Image

from pipeline.state import PipelineState
from services import document_ai

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

    # Scan all blocks once so material can be captured even when it appears
    # outside the notes section, such as in the title block.
    block_texts = []
    notes_text = []
    for block in raw_text_blocks:
        text = block.get("text", "").strip()
        if not text:
            continue
        block_texts.append(text)
        if NOTES_REGEX.search(text) or MATERIAL_REGEX.search(text):
            notes_text.append(text)

    all_text = "\n".join(block_texts)

    if notes_text:
        full_notes = "\n".join(notes_text)
        notes_result["raw_text"] = full_notes

        # Extract material
        material_match = MATERIAL_REGEX.search(full_notes) or MATERIAL_REGEX.search(all_text)
        if material_match:
            notes_result["material"] = material_match.group(1).strip()

    if notes_result["material"] is None:
        material_match = MATERIAL_REGEX.search(all_text)
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
        logger.debug("⚠️ OCR extraction failed: %s", str(exc))

    return title_result, bom_result


def _extract_via_document_ai(page_image_bytes: bytes) -> Dict:
    """
    Extract BOM table via Document AI.
    Falls back gracefully if Document AI fails or is not configured.
    Returns bom_result dict.
    """
    bom_result = {"rows": []}
    
    try:
        logger.debug("🤖 Attempting BOM extraction via Document AI")
        bom_result = document_ai.extract_tables(page_image_bytes)
        if bom_result.get("rows"):
            bom_result["extraction_source"] = "document_ai"
            logger.info("✓ Document AI extracted %d BOM rows", len(bom_result["rows"]))
        else:
            logger.debug("⚠️ Document AI returned no BOM rows")
    except Exception as exc:
        logger.debug("⚠️ Document AI extraction failed: %s", str(exc))
        bom_result = {"rows": [], "extraction_error": str(exc)}
    
    return bom_result


def _map_row_local(header_cells: List[str], row_cells: List[str]) -> Dict[str, str]:
    """Map header names to canonical BOM fields (simple local version)."""
    mapping = {
        "part_number": ["part", "part number", "pn", "item"],
        "description": ["description", "desc"],
        "quantity": ["qty", "quantity"],
        "notes": ["notes", "remark", "remarks"],
    }
    result = {"part_number": None, "description": None, "quantity": None, "notes": None}
    if header_cells:
        normalized = [" ".join(h.lower().split()) for h in header_cells]
        for idx, header in enumerate(normalized):
            for key, candidates in mapping.items():
                if header in candidates and idx < len(row_cells):
                    result[key] = row_cells[idx] or None
                    break
    else:
        if len(row_cells) > 0:
            result["part_number"] = row_cells[0] or None
        if len(row_cells) > 1:
            result["description"] = row_cells[1] or None
        if len(row_cells) > 2:
            result["quantity"] = row_cells[2] or None
        if len(row_cells) > 3:
            result["notes"] = row_cells[3] or None
    return result


def detect_table_opencv(page_image_bytes: bytes) -> Dict:
    """Detect table region with OpenCV and extract rows using pytesseract.

    Returns a dict: {"rows": [{part_number, description, quantity, notes}, ...], "extraction_source": "opencv"}
    """
    bom_result = {"rows": []}
    try:
        nparr = np.frombuffer(page_image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return bom_result

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 3)

        # Adaptive threshold on inverted grayscale for line extraction
        th = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2)

        # Extract horizontal lines
        horiz = th.copy()
        cols = horiz.shape[1]
        horiz_size = max(10, cols // 30)
        horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horiz_size, 1))
        horiz = cv2.erode(horiz, horiz_kernel, iterations=1)
        horiz = cv2.dilate(horiz, horiz_kernel, iterations=1)

        # Extract vertical lines
        vert = th.copy()
        rows = vert.shape[0]
        vert_size = max(10, rows // 30)
        vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vert_size))
        vert = cv2.erode(vert, vert_kernel, iterations=1)
        vert = cv2.dilate(vert, vert_kernel, iterations=1)

        # Combine line masks and close gaps so the table region forms one component.
        mask = cv2.bitwise_or(horiz, vert)
        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=1)

        # Find contours of table candidates.
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return bom_result

        # Choose largest contour by area, but ignore tiny intersection blobs.
        contours = [c for c in contours if cv2.contourArea(c) > 1000]
        if not contours:
            return bom_result

        c = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)
        if w * h < 5000:
            return bom_result

        table_crop = img[y : y + h, x : x + w]
        table_crop = cv2.resize(table_crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        # OCR the table crop by first estimating grid lines. This is much more stable
        # for scanned BOMs than OCR-ing the full table body in one pass.
        pil = Image.fromarray(cv2.cvtColor(table_crop, cv2.COLOR_BGR2RGB))
        crop_gray = cv2.cvtColor(table_crop, cv2.COLOR_BGR2GRAY)
        crop_th = cv2.adaptiveThreshold(
            ~crop_gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2
        )

        def _cluster_peaks(values: np.ndarray, min_distance: int = 12) -> List[int]:
            if values.size == 0:
                return []
            threshold = float(values.max()) * 0.5
            indices = np.where(values >= threshold)[0].tolist()
            if not indices:
                return []
            clusters = [[indices[0]]]
            for idx in indices[1:]:
                if idx - clusters[-1][-1] <= min_distance:
                    clusters[-1].append(idx)
                else:
                    clusters.append([idx])
            return [int(sum(cluster) / len(cluster)) for cluster in clusters]

        column_lines = _cluster_peaks(np.sum(crop_th, axis=0))
        row_lines = _cluster_peaks(np.sum(crop_th, axis=1))

        # Turn line positions into cell intervals.
        if len(column_lines) >= 3 and len(row_lines) >= 3:
            column_bounds = [0] + column_lines + [crop_th.shape[1] - 1]
            row_bounds = [0] + row_lines + [crop_th.shape[0] - 1]

            def _ocr_cell(cell_img: np.ndarray) -> str:
                cell_pil = Image.fromarray(cv2.cvtColor(cell_img, cv2.COLOR_BGR2RGB))
                text = pytesseract.image_to_string(cell_pil, config="--psm 7")
                return " ".join(text.split()).strip()

            grid_rows: List[List[str]] = []
            for top, bottom in zip(row_bounds[:-1], row_bounds[1:]):
                if bottom - top < 18:
                    continue
                row_cells: List[str] = []
                for left, right in zip(column_bounds[:-1], column_bounds[1:]):
                    if right - left < 18:
                        continue
                    pad = 3
                    y0 = max(0, top + pad)
                    y1 = min(crop_th.shape[0], bottom - pad)
                    x0 = max(0, left + pad)
                    x1 = min(crop_th.shape[1], right - pad)
                    if y1 <= y0 or x1 <= x0:
                        continue
                    cell_img = table_crop[y0:y1, x0:x1]
                    row_cells.append(_ocr_cell(cell_img))
                if any(row_cells):
                    grid_rows.append(row_cells)

            if grid_rows:
                header_cells = grid_rows[0]
                for row_cells in grid_rows[1:]:
                    mapped = _map_row_local(header_cells, row_cells)
                    if any(mapped.values()):
                        bom_result["rows"].append(mapped)

        if not bom_result["rows"]:
            data = pytesseract.image_to_data(pil, config="--psm 6", output_type=pytesseract.Output.DICT)
            df = pd.DataFrame(data)

            if df.empty:
                return bom_result

            # Group by line to reconstruct rows
            rows_text = []
            for line_num, group in df.groupby("line_num"):
                words = [str(t).strip() for t in group["text"].tolist() if str(t).strip()]
                line = " ".join(words)
                if line:
                    rows_text.append(line)

            if not rows_text:
                raw_text = pytesseract.image_to_string(pil, config="--psm 6")
                rows_text = [line.strip() for line in raw_text.splitlines() if line.strip()]

            if not rows_text:
                return bom_result

            # Assume first line is header if it contains keywords
            header_line = rows_text[0]
            header_cells = re.split(r"\s{2,}|\t", header_line)

            for line in rows_text[1:]:
                cells = re.split(r"\s{2,}|\t", line)
                mapped = _map_row_local(header_cells, cells)
                bom_result["rows"].append(mapped)

        if bom_result["rows"]:
            bom_result["extraction_source"] = "opencv"
    except Exception as exc:
        logger.debug("⚠️ OpenCV table detection failed: %s", str(exc))
    return bom_result


async def extract_structured_data(state: PipelineState) -> dict:
    """
    Extract title block, BOM table, and notes from raw_text_blocks.
    BOM extraction fallback chain: raw_text_blocks → OCR → Document AI
    """
    job_id = state.get("job_id", "unknown")
    logger.info("📋 Extracting structured data (title, BOM, notes)...")
    
    raw_text_blocks = state.get("raw_text_blocks") or []

    if raw_text_blocks:
        # Extract from raw_text_blocks
        logger.info("✓ Using raw_text_blocks from PDF extraction (%d blocks)", len(raw_text_blocks))
        title_result, notes_result, bom_result = _extract_from_raw_text_blocks(raw_text_blocks)
        title_result.setdefault("extraction_source", "raw_text_blocks")
        bom_result.setdefault("extraction_source", "raw_text_blocks")
        logger.info("✓ Title: %s | Notes: %d items | BOM: %d rows", 
                   title_result.get("title", "N/A")[:50], 
                   len(notes_result.get("general_notes", [])),
                   len(bom_result.get("rows", [])))
    else:
        # No raw_text_blocks: prefer Document AI for BOM extraction.
        logger.info("⚠️ No raw_text_blocks; using Document AI to extract BOM table")
        page_image_bytes = (state.get("page_images") or [None])[0]
        if not page_image_bytes:
            raise ValueError("page_images is required for Document AI extraction.")

        # Still run a quick OCR pass to capture title keywords for UI, but
        # rely on Document AI to produce BOM rows.
        try:
            title_result, _ = _extract_via_ocr(page_image_bytes)
        except Exception:
            title_result = {}

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

        # Primary BOM extraction when raw_text_blocks are missing
        bom_result = _extract_via_document_ai(page_image_bytes)

    return {
        "title_result": title_result,
        "notes_result": notes_result,
        "bom_result": bom_result,
    }


async def extract_notes(state: PipelineState) -> dict:
    """
    Extract notes (material, bullets) from raw_text_blocks using the existing helper.
    Returns a dict with `notes_result` for merging into pipeline state.
    """
    raw_text_blocks = state.get("raw_text_blocks") or []
    title_result, notes_result, bom_result = _extract_from_raw_text_blocks(raw_text_blocks)
    notes_result.setdefault("extraction_source", "raw_text_blocks" if raw_text_blocks else "none")
    return {"notes_result": notes_result}


async def extract_tables_node(state: PipelineState) -> dict:
    """
    Extract BOM / tables from page image using OpenCV+OCR primarily, with
    Document AI as an optional higher-cost fallback.
    Returns a dict with `bom_result`.
    """
    page_image_bytes = (state.get("page_images") or [None])[0]
    if not page_image_bytes:
        return {"bom_result": {"rows": [], "extraction_error": "page_images missing"}}

    # Preferred: OpenCV table detection + OCR
    bom_result = detect_table_opencv(page_image_bytes)
    if bom_result.get("rows"):
        return {"bom_result": bom_result}

    # Fallback: if OpenCV failed, try Document AI (more expensive)
    try:
        logger.info("⚠️ OpenCV didn't find BOM rows; trying Document AI as fallback")
        bom_result = _extract_via_document_ai(page_image_bytes)
    except Exception as exc:
        logger.debug("Document AI fallback failed: %s", str(exc))
        bom_result = {"rows": [], "extraction_error": str(exc)}

    return {"bom_result": bom_result}
