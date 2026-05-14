from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

from pipeline.state import PipelineState
from services import gcs
from utils.table_extraction import extract_bom_table

logger = logging.getLogger(__name__)


NOTES_REGEX = re.compile(r"\bnotes\b", re.IGNORECASE)
BULLET_REGEX = re.compile(r"^\s*(\d+)[\.\)]\s*(.+)$")
MATERIAL_REGEX = re.compile(r"\b(?:material|mat['\.]?l)[\s:]*([^\n]*)", re.IGNORECASE)


def _extract_notes_from_blocks(
    raw_text_blocks: List[dict],
) -> Dict:
    """Extract notes (material, bullets) from text blocks."""
    notes_result = {
        "material": None,
        "material_standard": None,
        "dimensional_notes": [],
        "surface_finish_notes": [],
        "process_notes": [],
        "general_notes": [],
        "raw_text": "",
    }

    if not raw_text_blocks:
        return notes_result

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

        material_match = MATERIAL_REGEX.search(full_notes) or MATERIAL_REGEX.search(all_text)
        if material_match:
            notes_result["material"] = material_match.group(1).strip()
    else:
        material_match = MATERIAL_REGEX.search(all_text)
        if material_match:
            notes_result["material"] = material_match.group(1).strip()

    bullets = []
    current_num = None
    current_text = ""

    for line in notes_result["raw_text"].split("\n"):
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

    return notes_result


def _extract_bom_from_pdf(pdf_gcs_path: str) -> Dict:
    """Extract the BOM table using the pdfplumber-based table extractor."""
    if not pdf_gcs_path:
        return {"rows": [], "extraction_error": "pdf_gcs_path is required for BOM extraction."}

    temp_path: Path | None = None
    try:
        source_path = Path(pdf_gcs_path)
        if source_path.exists():
            logger.debug("📄 Using local file for BOM extraction: %s", pdf_gcs_path)
            return extract_bom_table(source_path)

        if pdf_gcs_path.startswith("gs://"):
            logger.debug("📥 Downloading PDF from GCS for BOM extraction: %s", pdf_gcs_path)
            pdf_bytes = gcs.download_pdf(pdf_gcs_path)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_file.write(pdf_bytes)
                temp_path = Path(temp_file.name)
            logger.debug("✓ Downloaded PDF to temp: %s", temp_path)
            return extract_bom_table(temp_path)

        logger.debug("⚠ Unsupported PDF path format for BOM extraction: %s", pdf_gcs_path)
        return {"rows": [], "extraction_error": "Unsupported PDF path format for BOM extraction."}
    except Exception as exc:
        logger.debug("⚠️ BOM extraction failed: %s", str(exc))
        return {"rows": [], "extraction_error": str(exc)}
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


async def extract_structured_data(state: PipelineState) -> dict:
    """
    Extract notes (material, bullets) from raw_text_blocks.
    This node supplements the dedicated extraction nodes.
    Results from this node are merged into state alongside the dedicated nodes.
    """
    raw_text_blocks = state.get("raw_text_blocks") or []
    
    if not raw_text_blocks:
        return {
            "notes_result": {
                "material": None,
                "material_standard": None,
                "dimensional_notes": [],
                "surface_finish_notes": [],
                "process_notes": [],
                "general_notes": [],
                "raw_text": "",
                "extraction_source": "none",
            }
        }
    
    notes_result = _extract_notes_from_blocks(raw_text_blocks)
    notes_result.setdefault("extraction_source", "raw_text_blocks" if raw_text_blocks else "none")
    
    return {"notes_result": notes_result}


async def extract_tables_node(state: PipelineState) -> dict:
    """
    Extract BOM tables from the source PDF using pdfplumber and OCR validation.
    Only tables whose OCR text contains "BILL OF MATERIALS" are accepted.
    Returns a dict with `bom_result`.
    """
    pdf_gcs_path = state.get("pdf_gcs_path")
    if not pdf_gcs_path:
        return {"bom_result": {"rows": [], "extraction_error": "pdf_gcs_path missing"}}

    bom_result = _extract_bom_from_pdf(pdf_gcs_path)
    
    if bom_result.get("is_valid_bom") and bom_result.get("rows"):
        headers = bom_result.get("headers", [])
        mapped_rows = _map_extracted_rows(bom_result.get("rows", []), headers)
        bom_result["rows"] = mapped_rows
        bom_result["headers"] = headers
        bom_result.setdefault("extraction_source", "pdfplumber_ocr")
        logger.debug("✓ BOM extracted %d rows using pdfplumber", len(mapped_rows))
    elif not bom_result.get("extraction_error"):
        logger.debug("⚠ BOM extraction completed but BOM header validation failed")
        bom_result["extraction_error"] = "BOM header validation failed"
    else:
        logger.debug("⚠ BOM extraction returned no rows: %s", bom_result.get("extraction_error", "unknown"))
    
    return {"bom_result": bom_result}


def _normalize_header(header: str) -> str:
    """Normalize header variations to standard names."""
    import re
    header_lower = header.lower().strip()
    
    PATTERNS = [
        (r'part\s*no\.?|part\s*number', 'part_number'),
        (r'sap\s*no\.?', 'sap_no'),
        (r'covez|copez|codez|code\s*2', 'code2'),
        (r'desc\s*2|description\s*2', 'description2'),
        (r'vendor\s*part', 'vendor2'),
        (r'qty\.?|quantity', 'quantity'),
        (r'vendor', 'vendor'),
        (r'item', 'item'),
        (r'part', 'part_number'),
        (r'description', 'description'),
        (r'rev', 'rev'),
        (r'weight', 'weight'),
    ]
    
    for pattern, std_name in PATTERNS:
        if re.search(pattern, header_lower, re.IGNORECASE):
            return std_name
    
    return header_lower


def _map_extracted_rows(raw_rows: list, headers: list = None) -> list:
    """
    Map extracted table rows to BOM format.
    Uses header names when available, falls back to position.
    """
    if not raw_rows:
        return []
    
    # Standard BOM headers
    STANDARD_HEADERS = [
        "ITEM", "PART NO", "SAP NO", "CODE", "CODE2",
        "DESCRIPTION", "DESCRIPTION 2", "QTY", "REV",
        "VENDOR", "VENDOR PART", "WEIGHT"
    ]
    
    # Use provided headers or standard headers
    header_positions = []
    if headers:
        for h in headers:
            header_positions.append(_normalize_header(h))
    else:
        header_positions = [_normalize_header(h) for h in STANDARD_HEADERS]
    
    mapped_rows = []
    for row in raw_rows:
        mapped_row = {
            "item": None,
            "part_number": None,
            "sap_no": None,
            "code": None,
            "code2": None,
            "description": None,
            "description2": None,
            "quantity": None,
            "rev": None,
            "vendor": None,
            "vendor2": None,
            "weight": None,
        }
        
        num_cells = len(row)
        
        if header_positions and num_cells >= 4:
            for i, cell in enumerate(row):
                val = cell.strip() if isinstance(cell, str) else cell
                if i < len(header_positions):
                    field = header_positions[i]
                    if field in mapped_row:
                        mapped_row[field] = val
        else:
            if num_cells > 0:
                mapped_row["item"] = row[0].strip() if isinstance(row[0], str) else row[0]
            if num_cells > 1:
                mapped_row["part_number"] = row[1].strip() if isinstance(row[1], str) else row[1]
            if num_cells > 2:
                mapped_row["quantity"] = row[2].strip() if isinstance(row[2], str) else row[2]
            if num_cells > 3:
                mapped_row["rev"] = row[3].strip() if isinstance(row[3], str) else row[3]
            if num_cells > 4:
                mapped_row["vendor"] = row[4].strip() if isinstance(row[4], str) else row[4]
        
        mapped_rows.append(mapped_row)
    
    return mapped_rows
