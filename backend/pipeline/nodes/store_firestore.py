from __future__ import annotations

import logging

from pipeline.state import PipelineState
from services import firestore

logger = logging.getLogger(__name__)


async def store_firestore(state: PipelineState) -> dict:
	"""
	Persist final JSON and update job status in Firestore.
	"""
	job_id = state.get("job_id", "unknown")
	logger.info("💾 Storing results to Firestore...")
	
	final_json = state.get("final_json")
	if not final_json:
		raise ValueError("final_json is required before storing.")

	try:
		drawing_id = final_json.get("drawing_id", "")
		job_status = final_json.get("job_status", "failed")
		
		logger.info("📝 Storing drawing document (drawing_id=%s)", drawing_id)
		firestore.store_drawing(drawing_id, final_json)
		
		logger.info("🔔 Updating job status to '%s'", job_status)
		firestore.update_job_status(job_id, job_status)
		
		logger.info("✅ Successfully stored to Firestore")
	except NotImplementedError as exc:
		logger.error("❌ Firestore operation not implemented: %s", str(exc))
		raise RuntimeError(str(exc)) from exc

	return {"stored": True}
