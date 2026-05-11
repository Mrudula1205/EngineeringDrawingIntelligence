from __future__ import annotations

import logging

from pipeline.state import PipelineState
from services import gcs
from utils.pdf_utils import extract_text_blocks, rasterize_pdf

logger = logging.getLogger(__name__)


async def ingest_pdf(state: PipelineState) -> dict:
	"""
	Download from GCS, rasterize pages, extract text blocks.
	Returns partial updates for state.
	"""
	job_id = state.get("job_id", "unknown")
	existing_images = state.get("page_images") or []
	existing_blocks = state.get("raw_text_blocks") or []

	if existing_images and existing_blocks:
		logger.debug("📦 Using cached page images and text blocks (job_id=%s)", job_id)
		return {
			"page_images": existing_images,
			"raw_text_blocks": existing_blocks,
		}

	pdf_gcs_path = state.get("pdf_gcs_path")
	if not pdf_gcs_path:
		raise ValueError("pdf_gcs_path is required for ingest.")

	logger.info("📥 Downloading PDF from GCS: %s", pdf_gcs_path)
	try:
		pdf_bytes = gcs.download_pdf(pdf_gcs_path)
		logger.info("✓ PDF downloaded. Size: %.2f MB", len(pdf_bytes) / (1024 * 1024))
	except NotImplementedError as exc:
		logger.error("❌ GCS download failed: %s", str(exc))
		raise RuntimeError(str(exc)) from exc

	logger.info("🖼️ Rasterizing PDF pages (DPI=200)")
	page_images = rasterize_pdf(pdf_bytes, dpi=200)
	logger.info("✓ Rasterized %d pages", len(page_images))
	
	logger.info("📄 Extracting text blocks using Document AI")
	raw_text_blocks = extract_text_blocks(pdf_bytes)
	logger.info("✓ Extracted %d text blocks", len(raw_text_blocks))

	return {
		"page_images": page_images,
		"raw_text_blocks": raw_text_blocks,
	}
