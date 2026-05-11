from __future__ import annotations

from pipeline.nodes.region_utils import extract_text_in_bbox
from pipeline.state import PipelineState
from services import gemini


NOTES_EXTRACTION_PROMPT = """
You are analyzing the notes section of an engineering drawing.

Extract and structure the following from the raw notes text:

1. Material specification -- look for patterns like:
   - "MATERIAL: SS304"
   - "Material shall be [X] per [standard]"
   - "MAT'L: [X]"
   - Any reference to material grade, standard, or specification

2. Dimensional notes -- notes that refer to dimensions, tolerances, or geometric requirements

3. Surface finish notes

4. Heat treatment / process notes

5. All other notes (general notes, inspection requirements, etc.)

OUTPUT FORMAT -- respond ONLY with valid JSON, no preamble:
{
  "material": "<extracted material string | null>",
  "material_standard": "<e.g. ASTM A240 | null>",
  "dimensional_notes": ["<note text>"],
  "surface_finish_notes": ["<note text>"],
  "process_notes": ["<note text>"],
  "general_notes": ["<note text>"],
  "raw_text": "<full raw notes text>"
}
"""


async def extract_notes(state: PipelineState) -> dict:
	"""
	Extract notes using Gemini Flash on raw notes text.
	"""
	if state.get("region_type") != "notes":
		return {
			"material": None,
			"material_standard": None,
			"dimensional_notes": [],
			"surface_finish_notes": [],
			"process_notes": [],
			"general_notes": [],
			"raw_text": "",
			"extraction_error": "Notes region not detected.",
		}

	regions = state.get("regions") or {}
	notes_bbox = regions.get("bom_notes")
	if not notes_bbox:
		return {
			"material": None,
			"material_standard": None,
			"dimensional_notes": [],
			"surface_finish_notes": [],
			"process_notes": [],
			"general_notes": [],
			"raw_text": "",
			"extraction_error": "Notes region not found.",
		}

	text = extract_text_in_bbox(state.get("raw_text_blocks", []), notes_bbox, 0)
	result = gemini.extract_notes(text, NOTES_EXTRACTION_PROMPT)
	return result
