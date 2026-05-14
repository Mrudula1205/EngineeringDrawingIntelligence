from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Tuple

import fitz
from PIL import Image

logger = logging.getLogger(__name__)


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
