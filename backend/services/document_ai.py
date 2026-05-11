from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from google.cloud import documentai

logger = logging.getLogger(__name__)


def _get_required_env(key: str) -> str:
	value = os.getenv(key)
	if not value:
		raise RuntimeError(f"Missing required environment variable: {key}")
	return value


def _get_client() -> documentai.DocumentProcessorServiceClient:
	return documentai.DocumentProcessorServiceClient()


def _detect_mime_type(document_bytes: bytes) -> str:
	if document_bytes.startswith(b"%PDF"):
		return "application/pdf"
	if document_bytes.startswith(b"\x89PNG"):
		return "image/png"
	if document_bytes.startswith(b"\xff\xd8\xff"):
		return "image/jpeg"
	return "application/octet-stream"


def _layout_text(document: documentai.Document, layout: documentai.Document.Page.Layout) -> str:
	text = []
	for segment in layout.text_anchor.text_segments:
		start_index = int(segment.start_index or 0)
		end_index = int(segment.end_index or 0)
		text.append(document.text[start_index:end_index])
	return "".join(text).strip()


def _normalize_header(header: str) -> str:
	return " ".join(header.lower().split())


def _map_row(header_cells: List[str], row_cells: List[str]) -> Dict[str, Any]:
	mapping = {
		"part_number": ["part", "part number", "pn", "item"],
		"description": ["description", "desc"],
		"quantity": ["qty", "quantity"],
		"notes": ["notes", "remark", "remarks"],
	}
	result = {"part_number": None, "description": None, "quantity": None, "notes": None}
	if header_cells:
		normalized = [_normalize_header(value) for value in header_cells]
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


def extract_tables(document_bytes: bytes) -> Dict[str, Any]:
	_get_required_env("GOOGLE_CLOUD_PROJECT")
	_get_required_env("DOCUMENT_AI_PROCESSOR_ID")
	_get_required_env("DOCUMENT_AI_LOCATION")
	project_id = _get_required_env("GOOGLE_CLOUD_PROJECT")
	location = _get_required_env("DOCUMENT_AI_LOCATION")
	processor_id = _get_required_env("DOCUMENT_AI_PROCESSOR_ID")
	
	logger.debug("📊 Extracting tables using Document AI processor: %s", processor_id)
	name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

	client = _get_client()
	mime_type = _detect_mime_type(document_bytes)
	logger.debug("📄 Document MIME type: %s", mime_type)
	
	request = documentai.ProcessRequest(
		name=name,
		raw_document=documentai.RawDocument(content=document_bytes, mime_type=mime_type),
	)
	
	logger.debug("🤖 Calling Document AI API...")
	result = client.process_document(request=request)
	document = result.document
	logger.debug("✓ Document processed. Pages: %d", len(document.pages))

	rows: List[Dict[str, Any]] = []
	for page_idx, page in enumerate(document.pages):
		for table_idx, table in enumerate(page.tables):
			headers = []
			for header_row in table.header_rows:
				row_text = [
					_layout_text(document, cell.layout)
					for cell in header_row.cells
				]
				headers = row_text
				break
			for body_row in table.body_rows:
				cells = [_layout_text(document, cell.layout) for cell in body_row.cells]
				rows.append(_map_row(headers, cells))
		
		if page.tables:
			logger.debug("✓ Page %d: extracted %d table(s) with %d row(s)", page_idx + 1, len(page.tables), 
					   len([r for r in rows if r]))

	logger.debug("✓ Total %d table rows extracted", len(rows))
	return {"rows": rows, "extraction_error": None}
