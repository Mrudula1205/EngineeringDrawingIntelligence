from __future__ import annotations

import json
import logging

from pipeline.state import PipelineState
from services import gemini

logger = logging.getLogger(__name__)


TITLE_EXTRACTION_PROMPT = """
You are analyzing an engineering drawing to extract the title block information. 
The title block is typically located in a corner (usually bottom-right) of the drawing and contains metadata.

Using your understanding of standard engineering drawing title blocks, identify and extract all fields present.

Common fields to look for (not all will be present):
- Drawing number / part number / drawing ID
- Title / part name / description
- Company name / organization
- Revision / revision letter / rev level
- Date / drawn date / created date
- Scale (e.g., 1:50, 1:1, as noted)
- Sheet number / sheet of total
- Material / material specification (may be here or in notes)
- Drawn by / checked by / approved by / signatures
- Tolerances / general tolerances / tolerance note
- Weight / total weight
- Document type / drawing type

CRITICAL INSTRUCTIONS:
1. Look at the ENTIRE drawing, especially corners and margins
2. Extract ONLY values that you can clearly read or infer from the title block
3. If a field is not present or not readable, set it to null
4. Do NOT guess or invent values - if unsure, use null
5. If multiple material specifications exist (one in title block, one in notes), include only the one from the title block here

OUTPUT FORMAT -- respond ONLY with valid JSON, no preamble:
{
  "drawing_number": "<string or null>",
  "title": "<string or null>",
  "company": "<string or null>",
  "revision": "<string or null>",
  "date": "<string or null>",
  "scale": "<string or null>",
  "sheet": "<string or null>",
  "material": "<string or null>",
  "drawn_by": "<string or null>",
  "additional_fields": {
    "<field_name>": "<value>"
  },
  "fields_present": ["<list of field names that were actually found and have non-null values>"]
}
"""


async def extract_title(state: PipelineState) -> dict:
	"""
	Extract title block fields from the full page image using Gemini VLM.
	No region detection required - analyzes entire page.
	"""
	job_id = state.get("job_id", "unknown")
	logger.info("📋 Extracting title block using Gemini VLM...")
	
	page_image_bytes = (state.get("page_images") or [None])[0]
	if not page_image_bytes:
		raise ValueError("page_images is required for title extraction.")

	try:
		logger.info("🤖 Calling Gemini VLM for title block analysis...")
		result = gemini.extract_title_block(page_image_bytes, TITLE_EXTRACTION_PROMPT)
		
		fields_present = result.get("fields_present", [])
		if fields_present:
			logger.info("✓ Title block extracted! Found fields: %s", ", ".join(fields_present))
		else:
			logger.warning("⚠️ No title block fields extracted. May not be visible in this drawing.")
		
		return {"title_result": result}
	except Exception as exc:
		logger.error("❌ Title extraction failed: %s", str(exc))
		return {
			"title_result": {
				"drawing_number": None,
				"title": None,
				"company": None,
				"revision": None,
				"date": None,
				"scale": None,
				"sheet": None,
				"material": None,
				"drawn_by": None,
				"additional_fields": {},
				"fields_present": [],
				"extraction_error": str(exc),
			}
		}
