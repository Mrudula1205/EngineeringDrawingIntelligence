from __future__ import annotations

import io

from PIL import Image

from pipeline.nodes.region_utils import page_size_from_blocks, scale_bbox_to_image
from pipeline.state import PipelineState
from services import document_ai
from utils.pdf_utils import crop_image


async def extract_bom(state: PipelineState) -> dict:
	"""
	Use Document AI to extract BOM table from region crop.
	"""
	if state.get("region_type") != "bom":
		return {"rows": [], "extraction_error": "BOM region not detected."}

	regions = state.get("regions") or {}
	bom_bbox = regions.get("bom_notes")
	if not bom_bbox:
		return {"rows": [], "extraction_error": "BOM region not found."}

	page_image = state.get("page_images", [None])[0]
	if not page_image:
		raise ValueError("page_images is required for BOM extraction.")

	image = Image.open(io.BytesIO(page_image))
	page_size = page_size_from_blocks(state.get("raw_text_blocks", []), 0)
	image_bbox = scale_bbox_to_image(bom_bbox, page_size, image.size)
	region_image = crop_image(page_image, image_bbox)

	return document_ai.extract_tables(region_image)
