from __future__ import annotations

import logging
from datetime import datetime, timezone

from pipeline.state import PipelineState

logger = logging.getLogger(__name__)


def _collect_null_fields(title: dict, notes: dict, bom: dict, dimensions: dict) -> list[str]:
	missing = []
	if not title.get("drawing_number"):
		missing.append("title_block.drawing_number")
	if not title.get("title"):
		missing.append("title_block.title")
	if not notes.get("material") and not title.get("material"):
		missing.append("material")
	views = (dimensions.get("views") or {})
	if not views:
		missing.append("dimensions.views")
	# No hardcoded dimension keys: we only consider the presence of views
	# Specific missing dimension names are not enforced here.
	return missing


def _collect_inferred_dimensions(dimensions: dict) -> list[str]:
	"""
	VLM only extracts labeled dimensions, never infers.
	This function always returns an empty list.
	"""
	return []


def _min_confidence(dimensions: dict) -> float:
	min_score = 1.0
	views = dimensions.get("views") or {}
	for view in views.values():
		# Iterate all dict entries in the view and consider numeric confidences
		for dim_name, dim_val in view.items():
			if not isinstance(dim_val, dict):
				continue
			score = dim_val.get("confidence")
			if isinstance(score, (int, float)):
				min_score = min(min_score, float(score))
	return min_score


async def validate_merge(state: PipelineState) -> dict:
	"""
	Merge extraction outputs into final JSON and determine job status.
	No region detection used -- data comes from raw_text_blocks or OCR/VLM.
	"""
	job_id = state.get("job_id", "unknown")
	logger.info("🔄 Validating and merging extraction results...")
	
	errors = state.get("errors") or {}

	title = state.get("title_result") or {}
	notes = state.get("notes_result") or {}
	bom = state.get("bom_result") or {}
	dimensions = state.get("drawing_result") or {}

	# Check for extraction errors
	title_error = errors.get("title") or (title.get("extraction_error") or None)
	notes_error = errors.get("notes") or (notes.get("extraction_error") or None)
	bom_error = errors.get("bom") or (bom.get("extraction_error") or None)
	drawing_error = errors.get("drawing") or (dimensions.get("extraction_error") or None)

	# Store errors in results
	title.setdefault("extraction_error", title_error)
	notes.setdefault("extraction_error", notes_error)
	bom.setdefault("extraction_error", bom_error)
	if drawing_error:
		dimensions["extraction_error"] = drawing_error

	# Resolve material from notes or title
	material_resolved = notes.get("material") or title.get("material")
	if notes.get("material"):
		material_source = "notes"
	elif title.get("material"):
		material_source = "title_block"
	else:
		material_source = "null"

	# Determine job status based on required dimensions
	has_dimensions = bool((dimensions.get("views") or {}))
	null_fields = _collect_null_fields(title, notes, bom, dimensions)
	
	# Job is "completed" only if all required fields are present
	# Otherwise "partial" (some data extracted but incomplete)
	if drawing_error:
		job_status = "partial"
	elif len(null_fields) > 0:
		# Missing required fields means partial extraction
		job_status = "partial"
	elif has_dimensions:
		job_status = "completed"
	else:
		job_status = "partial"

	inferred_dims = _collect_inferred_dimensions(dimensions)
	min_conf = _min_confidence(dimensions)
	
	logger.info("✓ Status: %s | Material: %s (%s) | Missing: %d fields | Inferred: %d dims | Min confidence: %.2f",
			  job_status, material_resolved or "N/A", material_source, 
			  len(null_fields), len(inferred_dims), min_conf)
	
	if null_fields:
		logger.warning("⚠️ Missing fields: %s", ", ".join(null_fields[:5]))
	
	final_json = {
		"drawing_id": state.get("drawing_id"),
		"job_id": state.get("job_id"),
		"job_status": job_status,
		"processed_at": datetime.now(timezone.utc).isoformat(),
		"source_gcs_path": state.get("pdf_gcs_path"),
		"unit_original": dimensions.get("unit_original", "mm"),
		"unit_normalized": "mm",
		"title_block": title,
		"bom": bom,
		"notes": notes,
		"dimensions": dimensions,
		"material_resolved": material_resolved,
		"material_source": material_source,
		"extraction_summary": {
			"null_fields": null_fields,
			"inferred_dimensions": inferred_dims,
			"min_confidence_score": min_conf,
		},
	}

	return final_json
