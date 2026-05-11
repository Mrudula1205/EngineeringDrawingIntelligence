from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Tuple

import fitz
from PIL import Image

logger = logging.getLogger(__name__)


def extract_vector_drawings(pdf_bytes: bytes) -> List[Dict[str, Any]]:
	"""
	Extract vector drawing primitives metadata from each page using PyMuPDF.
	
	This is useful as a pre-OCR/VLM signal for geometry-heavy engineering drawings.
	Returns one summary dict per page.
	"""
	logger.debug("📐 Extracting vector drawing metadata from PDF")
	page_summaries: List[Dict[str, Any]] = []

	with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
		for page_index, page in enumerate(doc):
			drawings = page.get_drawings()
			line_count = 0
			curve_count = 0
			rect_count = 0
			quad_count = 0
			other_primitive_count = 0
			stroke_count = 0
			fill_count = 0
			min_x = None
			min_y = None
			max_x = None
			max_y = None

			for drawing in drawings:
				items = drawing.get("items") or []
				if drawing.get("color") is not None:
					stroke_count += 1
				if drawing.get("fill") is not None:
					fill_count += 1

				rect = drawing.get("rect")
				if rect is not None:
					x0, y0, x1, y1 = float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)
					min_x = x0 if min_x is None else min(min_x, x0)
					min_y = y0 if min_y is None else min(min_y, y0)
					max_x = x1 if max_x is None else max(max_x, x1)
					max_y = y1 if max_y is None else max(max_y, y1)

				for item in items:
					if not item:
						continue
					tag = item[0]
					if tag == "l":
						line_count += 1
					elif tag == "c":
						curve_count += 1
					elif tag == "re":
						rect_count += 1
					elif tag == "qu":
						quad_count += 1
					else:
						other_primitive_count += 1

			page_summaries.append(
				{
					"page": page_index,
					"drawings_count": len(drawings),
					"primitive_counts": {
						"line": line_count,
						"curve": curve_count,
						"rect": rect_count,
						"quad": quad_count,
						"other": other_primitive_count,
					},
					"style_counts": {
						"stroke_paths": stroke_count,
						"fill_paths": fill_count,
					},
					"extent": {
						"x0": min_x,
						"y0": min_y,
						"x1": max_x,
						"y1": max_y,
					},
				}
			)

	logger.debug("✓ Extracted vector drawing metadata for %d page(s)", len(page_summaries))
	return page_summaries


def rasterize_pdf(pdf_bytes: bytes, dpi: int = 200) -> List[bytes]:
	"""
	Returns a list of page images in PNG bytes.
	"""
	if dpi < 72:
		raise ValueError("dpi must be >= 72")

	logger.debug("🖼️ Rasterizing PDF at %d DPI", dpi)
	images: List[bytes] = []
	with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
		num_pages = doc.page_count
		logger.debug("📄 PDF has %d page(s)", num_pages)
		for page_idx, page in enumerate(doc):
			matrix = fitz.Matrix(dpi / 72, dpi / 72)
			pix = page.get_pixmap(matrix=matrix, alpha=False)
			img_bytes = pix.tobytes("png")
			images.append(img_bytes)
			logger.debug("✓ Page %d rasterized (size: %.2f KB)", page_idx + 1, len(img_bytes) / 1024)
	
	logger.debug("✓ Total %d images created", len(images))
	return images


def extract_text_blocks(pdf_bytes: bytes) -> List[Dict[str, Any]]:
	"""
	Returns raw text blocks with bounding boxes for all pages.
	"""
	logger.debug("📄 Extracting text blocks from PDF")
	blocks: List[Dict[str, Any]] = []
	with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
		num_pages = doc.page_count
		logger.debug("📋 PDF has %d page(s)", num_pages)
		for page_index, page in enumerate(doc):
			page_blocks = page.get_text("blocks")
			for block in page_blocks:
				x0, y0, x1, y1, text, _, block_type = block
				blocks.append(
					{
						"page": page_index,
						"bbox": [float(x0), float(y0), float(x1), float(y1)],
						"text": text,
						"type": block_type,
					}
				)
			logger.debug("✓ Page %d: extracted %d blocks", page_index + 1, len([b for b in blocks if b["page"] == page_index]))
	
	logger.debug("✓ Total %d text blocks extracted", len(blocks))
	return blocks


def crop_image(page_image: bytes, bbox: Tuple[float, float, float, float]) -> bytes:
	"""
	Returns cropped image bytes for a bbox in page coordinates.
	"""
	image = Image.open(io.BytesIO(page_image))
	image.load()
	width, height = image.size

	x0, y0, x1, y1 = bbox
	left = max(0, min(int(x0), width))
	top = max(0, min(int(y0), height))
	right = max(0, min(int(x1), width))
	bottom = max(0, min(int(y1), height))

	if right <= left or bottom <= top:
		raise ValueError("Invalid crop bbox after clamping.")

	cropped = image.crop((left, top, right, bottom))
	buffer = io.BytesIO()
	cropped.save(buffer, format="PNG")
	return buffer.getvalue()
