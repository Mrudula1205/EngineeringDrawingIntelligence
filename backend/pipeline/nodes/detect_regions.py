from __future__ import annotations

import io
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import pytesseract
from PIL import Image

from pipeline.state import PipelineState


def _get_engineering_title_block(img: Image.Image) -> Tuple[float, float, float, float] | None:
	"""
	Detect title block using Tesseract OCR and keyword anchoring.
	Looks for bottom-right quadrant with title block keywords.
	"""
	try:
		w, h = img.size

		# Run Tesseract to get TSV data
		data = pytesseract.image_to_data(img, config="--psm 3", output_type=pytesseract.Output.DICT)
		df = pd.DataFrame(data)

		# Filter for bottom-right quadrant with non-empty, confident text
		df_br = df[
			(df['left'] > 0.55 * w) & 
			(df['top'] > 0.45 * h) & 
			(df['text'].str.strip() != "") & 
			(df['conf'] > 0)
		].copy()

		if df_br.empty:
			return None

		# Define title block keywords
		keywords = ["title", "dwg", "rev", "sheet", "scale", "weight", "size", "no.", "projection", "drawing"]
		pattern = '|'.join(keywords)
		df_br['text_lower'] = df_br['text'].astype(str).str.lower()
		anchors = df_br[df_br['text_lower'].str.contains(pattern, na=False)]

		if anchors.empty:
			return None

		# Find bounding box from anchor keywords
		min_left = anchors['left'].min()
		min_top = anchors['top'].min()

		padding = 45
		x0 = max(int(0.5 * w), int(min_left - padding))
		y0 = max(int(0.4 * h), int(min_top - padding))
		x1 = int(w - 5)
		y1 = int(h - 5)

		return (float(x0), float(y0), float(x1), float(y1))
	except Exception as exc:
		print(f"Warning: Title block detection failed: {exc}")
		return None


def _get_bom_table_region(img: Image.Image, blocks: List[dict]) -> Tuple[float, float, float, float] | None:
	"""
	Detect BOM table using Tesseract OCR and keyword anchoring.
	Looks for "BOM", "Bill of Materials", "Qty" keywords.
	"""
	try:
		w, h = img.size

		# Run Tesseract to get TSV data
		data = pytesseract.image_to_data(img, config="--psm 3", output_type=pytesseract.Output.DICT)
		df = pd.DataFrame(data)

		# Filter for non-empty, confident text
		df_clean = df[
			(df['text'].str.strip() != "") & 
			(df['conf'] > 30)
		].copy()

		if df_clean.empty:
			return None

		# Define BOM keywords
		keywords = ["bom", "bill of material", "bill of materials", "qty", "quantity", "part", "description"]
		pattern = '|'.join(keywords)
		df_clean['text_lower'] = df_clean['text'].astype(str).str.lower()
		anchors = df_clean[df_clean['text_lower'].str.contains(pattern, na=False)]

		if anchors.empty:
			return None

		# Find BOM anchor (topmost occurrence typically)
		anchor_top = anchors['top'].min()
		anchor_left = anchors['left'].min()

		# Estimate BOM table bounds (typically left side, below anchor)
		padding = 30
		x0 = max(0.0, anchor_left - padding)
		y0 = max(0.0, anchor_top - padding)
		x1 = min(float(w), 0.55 * w)  # BOM usually on left half
		y1 = min(float(h), anchor_top + 0.35 * h)  # Typical BOM height

		return (x0, y0, x1, y1)
	except Exception as exc:
		print(f"Warning: BOM table detection failed: {exc}")
		return None



	max_x = 0.0
	max_y = 0.0
	for block in blocks:
		bbox = block.get("bbox") or []
		if len(bbox) == 4:
			max_x = max(max_x, float(bbox[2]))
			max_y = max(max_y, float(bbox[3]))
	return max_x, max_y


def _sum_text_density(blocks: List[dict], region: Tuple[float, float, float, float]) -> int:
	left, top, right, bottom = region
	count = 0
	for block in blocks:
		bbox = block.get("bbox") or []
		if len(bbox) != 4:
			continue
		x0, y0, x1, y1 = bbox
		cx = (x0 + x1) / 2
		cy = (y0 + y1) / 2
		if left <= cx <= right and top <= cy <= bottom:
			text = (block.get("text") or "").strip()
			count += len(text)
	return count


def _infer_region_type(region_text: str) -> str:
	text = region_text.lower()
	keywords = ["bom", "bill of material", "qty", "quantity"]
	return "bom" if any(keyword in text for keyword in keywords) else "notes"


async def detect_regions(state: PipelineState) -> dict:
	"""
	Detect title, BOM/notes, and drawing regions using OCR-based keyword anchoring.
	Falls back to heuristics if OCR detection fails.
	"""
	if not state.get("page_images"):
		raise ValueError("page_images is required for region detection.")

	blocks = [b for b in state.get("raw_text_blocks", []) if b.get("page") == 0]
	page_width, page_height = _page_size_from_blocks(blocks)
	if page_width <= 0 or page_height <= 0:
		image = Image.open(io.BytesIO(state["page_images"][0]))
		page_width, page_height = image.size

	# Load page image for OCR
	page_image = Image.open(io.BytesIO(state["page_images"][0])).convert("RGB")

	# Try OCR-based title block detection
	title_bbox = _get_engineering_title_block(page_image)
	if not title_bbox:
		# Fallback to heuristic
		title_bbox = (
			0.7 * page_width,
			0.8 * page_height,
			page_width,
			page_height,
		)

	# Try OCR-based BOM table detection
	bom_bbox = _get_bom_table_region(page_image, blocks)
	if not bom_bbox:
		# Fallback to heuristic (left half of page)
		left = 0.0
		top = 0.0
		right = page_width
		bottom = page_height

		quadrant_top_left = (left, top, 0.5 * right, 0.5 * bottom)
		quadrant_bottom_left = (left, 0.5 * bottom, 0.5 * right, bottom)

		min_density = 20
		top_left_density = _sum_text_density(blocks, quadrant_top_left)
		bom_bbox = quadrant_top_left if top_left_density >= min_density else quadrant_bottom_left

	# Infer region type from BOM region text
	region_text = " ".join(
		(b.get("text") or "")
		for b in blocks
		if bom_bbox[0] <= (b.get("bbox") or [0, 0, 0, 0])[0] <= bom_bbox[2]
	)
	region_type = _infer_region_type(region_text)

	# Define drawing region as remaining space (exclude title and BOM regions)
	draw_left, draw_top, draw_right, draw_bottom = 0.0, 0.0, page_width, page_height
	margin = 0.02 * min(page_width, page_height)
	title_x0, title_y0, _, _ = title_bbox
	candidate_right = title_x0 + margin
	candidate_bottom = title_y0 + margin
	if (candidate_right - draw_left) / page_width >= 0.6:
		draw_right = candidate_right
	if (candidate_bottom - draw_top) / page_height >= 0.6:
		draw_bottom = candidate_bottom

	drawing_bbox = (draw_left, draw_top, draw_right, draw_bottom)

	return {
		"regions": {
			"title": title_bbox,
			"bom_notes": bom_bbox,
			"drawing": drawing_bbox,
		},
		"region_type": region_type,
	}
