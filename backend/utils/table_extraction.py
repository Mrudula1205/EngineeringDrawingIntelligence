"""
Table extraction utilities using pdfplumber and pytesseract.
Provides functions to extract BOM tables from PDFs with text validation.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import pdfplumber
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)


def _ocr_with_tesseract(roi_bytes: bytes) -> str:
    """Run pytesseract OCR on an image and return text."""
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(roi_bytes))
    img_np = np.array(img)

    if len(img_np.shape) == 2:
        gray = img_np
    else:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)

    text = pytesseract.image_to_string(
        gray,
        config='--psm 6',
        lang='eng'
    )
    return text


def _detect_table_lines(img_gray: np.ndarray) -> dict:
    """Detect vertical and horizontal lines in table image."""
    _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 30))
    vertical_lines = cv2.erode(binary, vertical_kernel, iterations=2)
    vertical_lines = cv2.dilate(vertical_lines, vertical_kernel, iterations=2)

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    horizontal_lines = cv2.erode(binary, horizontal_kernel, iterations=2)
    horizontal_lines = cv2.dilate(horizontal_lines, horizontal_kernel, iterations=2)

    v_contours, _ = cv2.findContours(vertical_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    v_lines = []
    for cnt in v_contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 10 and h > 20:
            v_lines.append(x + w // 2)

    h_contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h_lines = []
    for cnt in h_contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h < 10 and w > 20:
            h_lines.append(y + h // 2)

    return {"vertical": sorted(set(v_lines)), "horizontal": sorted(set(h_lines))}


def _ocr_cell_by_line_detection(img_gray: np.ndarray, dpi: int = 300) -> list[list[str]]:
    """Extract table data by detecting lines and OCR each cell."""
    lines = _detect_table_lines(img_gray)
    v_lines = lines["vertical"]
    h_lines = lines["horizontal"]

    if len(v_lines) < 3 or len(h_lines) < 2:
        return []

    v_lines = [0] + sorted(v_lines) + [img_gray.shape[1]]
    h_lines = [0] + sorted(h_lines) + [img_gray.shape[0]]

    rows_data = []

    for i in range(len(h_lines) - 1):
        row_cells = []
        y_top = max(0, h_lines[i] + 2)
        y_bottom = min(img_gray.shape[0], h_lines[i + 1] - 2)

        for j in range(len(v_lines) - 1):
            x_left = max(0, v_lines[j] + 2)
            x_right = min(img_gray.shape[1], v_lines[j + 1] - 2)

            if x_right > x_left and y_bottom > y_top:
                cell_roi = img_gray[y_top:y_bottom, x_left:x_right]

                if cell_roi.size > 0 and cell_roi.shape[0] > 5 and cell_roi.shape[1] > 5:
                    _, cell_encoded = cv2.imencode('.png', cell_roi)
                    cell_bytes = cell_encoded.tobytes()

                    text = _ocr_with_tesseract(cell_bytes)
                    cell_text = text.strip().replace('\n', ' ').replace('\r', ' ')
                    row_cells.append(cell_text)
                else:
                    row_cells.append("")

        if row_cells and any(row_cells):
            rows_data.append(row_cells)

    return rows_data


def extract_table_contents_from_pdf(
    pdf_path: str | Path,
    min_width: int = 2000,
    min_height: int = 200,
    padding: int = 50,
    dpi: int = 300,
) -> List[Dict[str, Any]]:
    """
    Extract table contents from PDF using pdfplumber.

    Args:
        pdf_path: Path to PDF file
        min_width: Minimum table width in pixels
        min_height: Minimum table height in pixels
        padding: Padding around table bounds
        dpi: DPI for image rendering

    Returns:
        List of extracted tables with metadata and row data
    """
    results = []
    pdf_path = Path(pdf_path)

    logger.debug("Extracting tables from PDF: %s at %d DPI", pdf_path, dpi)

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "intersection_tolerance": 5,
                }

                tables = page.extract_tables(table_settings=table_settings)
                bounds = page.find_tables(table_settings=table_settings)

                scale = dpi / 72

                for table_idx, table in enumerate(tables):
                    if table_idx >= len(bounds):
                        continue

                    bbox = bounds[table_idx].bbox
                    if not bbox:
                        continue

                    x1, y1, x2, y2 = bbox
                    x1 = max(0, int(x1 * scale) - padding)
                    y1 = max(0, int(y1 * scale) - padding)
                    x2 = int(x2 * scale) + padding
                    y2 = int(y2 * scale) + padding

                    width = x2 - x1
                    height = y2 - y1

                    if width >= min_width and height >= min_height:
                        table_data = {
                            "page": page_num + 1,
                            "table_index": table_idx + 1,
                            "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                            "dimensions": {"width": width, "height": height},
                            "rows": [],
                        }

                        for row in table:
                            cleaned_row = [
                                cell.strip() if cell and isinstance(cell, str) else ""
                                for cell in row
                            ]
                            if any(cleaned_row):
                                table_data["rows"].append(cleaned_row)

                        results.append(table_data)

        logger.debug("Extracted %d table(s) from PDF", len(results))
    except Exception as e:
        logger.error("Error extracting tables from PDF: %s", str(e))
        raise

    return results


STANDARD_BOM_HEADERS = [
    "ITEM", "PART NO", "SAP NO", "CODE", "CODE2",
    "DESCRIPTION", "DESCRIPTION 2", "QTY", "REV",
    "VENDOR", "VENDOR PART", "WEIGHT"
]


def _normalize_row_columns(row: list[str], target_cols: int) -> list[str]:
    """Split or pad row to match target column count."""
    current_cols = len(row)

    if current_cols == target_cols:
        return row

    if current_cols < target_cols:
        result = row + [""] * (target_cols - current_cols)
    else:
        result = list(row)

        while len(result) > target_cols:
            max_idx = max(range(len(result)), key=lambda i: len(result[i]))
            cell = result[max_idx]

            if ' ' in cell and len(cell) > 15:
                parts = cell.rsplit(' ', 1)
                if len(parts) == 2 and len(parts[0]) > 3:
                    result[max_idx:max_idx+1] = parts
                else:
                    if max_idx > 0:
                        result[max_idx-1] = result[max_idx-1] + " " + result[max_idx]
                        del result[max_idx]
                    else:
                        break
            else:
                break

        while len(result) > target_cols:
            result[-2] = result[-2] + " " + result[-1]
            del result[-1]

        while len(result) < target_cols:
            result.append("")

    return result[:target_cols]


def _parse_ocr_table(ocr_text: str) -> tuple[list[list[str]], list[str] | None]:
    """
    Parse OCR text into table rows.
    Handles pipe-delimited and space-aligned formats.
    Returns (rows, headers) where headers are extracted if detected.
    """
    if not ocr_text:
        return [], STANDARD_BOM_HEADERS.copy()

    BOM_TITLE_PATTERNS = [
        r'\bBILL\s+OF\s+MATERIALS\b',
        r'\bBILL\s+OF\s+MATL\b',
        r'\bPARTS\s+LIST\b',
    ]

    import re

    raw_rows = []
    for line in ocr_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        if '|' in line:
            cells = [c.strip() for c in line.split('|')]
            cells = [c for c in cells if c and c != '-']
            if cells:
                raw_rows.append(cells)
        else:
            cells = [c.strip() for c in line.split() if c.strip()]
            if cells and len(cells) >= 2:
                raw_rows.append(cells)

    filtered_rows = []
    for row in raw_rows:
        row_text = ' '.join(row).upper()
        if any(re.search(p, row_text, re.IGNORECASE) for p in BOM_TITLE_PATTERNS):
            continue
        filtered_rows.append(row)

    headers = None
    COLUMN_HEADER_KEYWORDS = {"ITEM", "PARTNO", "SAP", "DESCRIPTION", "QTY", "QUANTITY", "REV", "NOTES", "VENDOR"}

    header_idx = None
    for i, row in enumerate(filtered_rows):
        row_text = ' '.join(row).upper()
        matches = sum(1 for kw in COLUMN_HEADER_KEYWORDS if kw in row_text)
        if matches >= 3:
            header_idx = i
            headers = _split_merged_headers(row)
            break

    if header_idx is not None:
        data_rows = filtered_rows[:header_idx]
    else:
        data_rows = filtered_rows

    if not headers or len(headers) < 4:
        headers = STANDARD_BOM_HEADERS.copy()

    target_cols = len(headers)
    normalized_rows = []
    for row in data_rows:
        normalized_row = _normalize_row_columns(row, target_cols)
        normalized_rows.append(normalized_row)

    return normalized_rows, headers


def _split_merged_headers(header_row: list[str]) -> list[str]:
    """Split merged header cells into individual headers."""
    import re

    PATTERN_MAP = [
        (r'\bPART\s*NO\.?\b|\bPART\s*NUMBER\b|\bPARTNO\b', 'PART NO'),
        (r'\bSAP\s*NO\.?\b|\bSAP\s*NUMBER\b|\bSAPNO\b', 'SAP NO'),
        (r'\bCODE\s*2\b|\bCODE2\b|\bCOVEZ\b|\bCOPEZ\b|\bCODEZ\b|\bCOPE\b|\bCOP\b', 'CODE2'),
        (r'\bDESC\s*2\b|\bDESCRIPTION\s*2\b', 'DESCRIPTION 2'),
        (r'\bITEM\b', 'ITEM'),
        (r'\bDESCRIPTION\b', 'DESCRIPTION'),
        (r'\bCODE\b(?!\s*2)', 'CODE'),
        (r'\bVENDOR\s*PART\b', 'VENDOR PART'),
        (r'\bQTY\.?\b|\bQUANTITY\b', 'QTY'),
        (r'\bREV\.?\b', 'REV'),
        (r'\bVENDOR\b(?!\s*PART)', 'VENDOR'),
        (r'\bWEIGHT\b', 'WEIGHT'),
    ]

    SKIP_CELLS = {'NO', '2', 'OF', 'AND', 'THE'}

    result = []

    for cell in header_row:
        cell_upper = cell.upper().strip()
        if not cell_upper or len(cell_upper) <= 1:
            continue

        cell_matches = []
        for pattern, std_name in PATTERN_MAP:
            if re.search(pattern, cell_upper, re.IGNORECASE):
                cell_matches.append(std_name)

        if cell_matches:
            result.extend(cell_matches)
        elif cell_upper not in SKIP_CELLS:
            result.append(cell.strip())

    return result


def extract_bom_table(
    pdf_path: str | Path,
    validate_bom_header: bool = True,
    min_width: int = 500,
    min_height: int = 200,
    padding: int = 50,
    dpi: int = 300,
) -> Dict[str, Any]:
    """
    Extract BOM table from PDF with validation using pytesseract OCR.
    Uses line detection to find table structure and OCR to extract text.

    Args:
        pdf_path: Path to PDF file
        validate_bom_header: If True, validates that extracted text contains BOM headers
        min_width: Minimum table width in pixels
        min_height: Minimum table height in pixels
        padding: Padding around table bounds
        dpi: DPI for image rendering

    Returns:
        Dictionary with table data and validation status
    """
    pdf_path = Path(pdf_path)
    logger.debug("Extracting BOM table from: %s", pdf_path)

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                img = page.to_image(resolution=dpi).original
                img_cv = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)

                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "intersection_tolerance": 5,
                }

                tables = page.extract_tables(table_settings=table_settings)
                bounds = page.find_tables(table_settings=table_settings)

                logger.debug("Page %d: Found %d tables", page_num + 1, len(tables))

                scale = dpi / 72

                for table_idx, table in enumerate(tables):
                    if table_idx >= len(bounds):
                        continue

                    bbox = bounds[table_idx].bbox
                    if not bbox:
                        continue

                    x1, y1, x2, y2 = bbox
                    x1 = max(0, int(x1 * scale) - padding)
                    y1 = max(0, int(y1 * scale) - padding)
                    x2 = int(x2 * scale) + padding
                    y2 = int(y2 * scale) + padding

                    width = x2 - x1
                    height = y2 - y1

                    logger.debug("Table %d: bbox=(%d,%d,%d,%d), size=%dx%d", table_idx+1, x1, y1, x2, y2, width, height)

                    if width >= min_width and height >= min_height:
                        gray = cv2.cvtColor(img_cv[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)

                        rows = _ocr_cell_by_line_detection(gray, dpi)

                        if not rows:
                            logger.debug("No rows from line detection, trying region OCR")
                            _, roi_encoded = cv2.imencode('.png', img_cv[y1:y2, x1:x2])
                            roi_bytes = roi_encoded.tobytes()
                            ocr_text = _ocr_with_tesseract(roi_bytes)
                            rows, detected_headers = _parse_ocr_table(ocr_text)
                            headers = detected_headers if detected_headers else STANDARD_BOM_HEADERS.copy()
                        else:
                            headers = STANDARD_BOM_HEADERS.copy()

                        is_valid_bom = True
                        if validate_bom_header and headers:
                            headers_text = ' '.join(headers).upper()
                            is_valid_bom = any(kw in headers_text for kw in ["BILL OF MATERIAL", "BOM", "BILL OF MATL", "PARTS LIST", "ITEM", "PART", "DESCRIPTION"])
                            logger.debug("BOM validation: %s", "PASSED" if is_valid_bom else "FAILED")

                        if not is_valid_bom:
                            logger.debug("Skipping table - BOM header not found")
                            continue

                        if rows:
                            target_cols = len(headers) if headers else 12
                            normalized_rows = []
                            for row in rows:
                                normalized_row = _normalize_row_columns(row, target_cols)
                                normalized_rows.append(normalized_row)
                            rows = normalized_rows

                        logger.debug("Extracted %d rows from table", len(rows) if rows else 0)

                        table_data = {
                            "page": page_num + 1,
                            "table_index": table_idx + 1,
                            "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                            "dimensions": {"width": width, "height": height},
                            "rows": rows,
                            "headers": headers,
                            "is_valid_bom": is_valid_bom,
                        }

                        if rows:
                            logger.debug(
                                "Extracted BOM table from page %d: %d rows",
                                page_num + 1,
                                len(table_data["rows"]),
                            )
                            return table_data

        logger.warning("No valid BOM table found in PDF")
        return {"rows": [], "is_valid_bom": False, "error": "No valid BOM table found"}

    except Exception as e:
        logger.error("Error extracting BOM table: %s", str(e))
        return {"rows": [], "is_valid_bom": False, "error": str(e)}