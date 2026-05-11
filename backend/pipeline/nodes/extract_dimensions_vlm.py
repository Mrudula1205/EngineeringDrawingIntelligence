from __future__ import annotations

import json
import logging

from pipeline.state import PipelineState
from services import gemini

logger = logging.getLogger(__name__)


DIMENSIONS_EXTRACTION_PROMPT = """
You are a technical drawing analyst. Extract ONLY explicit, labeled dimensions from the drawing.

CRITICAL: Do NOT infer, estimate, or derive dimensions from geometry. Only extract values that are clearly labeled.

INSTRUCTIONS:
1. Look for dimensional text labels that clearly show numeric values (e.g., "25 mm", "1.5 in", "R10")
2. These are marked with dimension lines, arrows, circles, or explicit text annotations
3. For each view (TOP, BOTTOM, FRONT, SIDE, SECTION, etc.), extract:
   - Any radius/diameter marked (R, Ø, D)
   - Any length/width marked
   - Any thickness marked
   - Any other explicitly labeled dimensions

4. Extract EXACTLY as labeled - NO modifications:
   - Keep numeric values unchanged
   - Keep units as shown (mm, in, cm, etc.)
   - Use clear, descriptive dimension names (e.g., "inner_radius", "hole_diameter", "bolt_circle_diameter")
   - If unsure about a value or unit, SKIP IT (do not include it in response)

RESPONSE FORMAT - VALID JSON ONLY:
{
  "views": {
    "<VIEW_NAME>": {
      "<dimension_name>": {
        "value": <number or null>,
        "unit": "<unit as shown>" or null,
        "confidence": <0.0 to 1.0 confidence in the extraction>
      },
      ...more dimensions...
    },
    ...more views...
  },
  "extraction_notes": "<brief summary: which views found, any missing or uncertain dimensions>"
}

RULES:
- Set field to null only if you see the dimension labeled but cannot read the value
- Do NOT create dimensions that aren't explicitly labeled
- confidence: 1.0 for clear, legible labeled dimensions; lower for unclear/ambiguous text
- Skip any dimension you cannot confidently read
- Each dimension is a direct key under the view (no nested arrays)
"""


async def extract_dimensions_vlm(state: PipelineState) -> dict:
	"""
	Extract dimensions from the full PDF page image using Gemini VLM.
	Analyzes spatial understanding of the drawing.
	"""
	job_id = state.get("job_id", "unknown")
	logger.info("📐 Extracting dimensions using Gemini VLM (gemini-2.0-flash)...")
	
	page_image_bytes = (state.get("page_images") or [None])[0]
	if not page_image_bytes:
		raise ValueError("page_images is required for dimension extraction.")

	logger.info("✓ Page image loaded. Size: %.2f MB", len(page_image_bytes) / (1024 * 1024))
	
	try:
		logger.info("🤖 Calling Gemini VLM for dimension analysis...")
		result = gemini.extract_drawing_dimensions(page_image_bytes, DIMENSIONS_EXTRACTION_PROMPT)
		
		views = result.get("views") or {}
		if views:
			logger.info("✓ Dimensions extracted! Found %d view(s): %s", 
					   len(views), ", ".join(views.keys()))
		else:
			logger.warning("⚠️ No dimensions found in drawing. Extraction notes: %s", 
						  result.get("extraction_notes", "N/A"))
		
		return {"drawing_result": result}
	except Exception as exc:
		logger.error("❌ VLM extraction failed: %s", str(exc))
		return {
			"drawing_result": {
				"views": {},
				"extraction_error": str(exc),
				"extraction_notes": f"VLM extraction failed: {str(exc)}",
			}
		}
