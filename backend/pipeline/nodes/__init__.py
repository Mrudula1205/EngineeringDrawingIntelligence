from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from pipeline.state import PipelineState

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

logger = logging.getLogger(__name__)


async def with_retry(
	func: Callable[[PipelineState], Awaitable[dict]],
	state: PipelineState,
	node_name: str,
	result_key: Optional[str],
	update_errors: bool = True,
) -> Dict[str, Any]:
	"""
	Retry wrapper for pipeline nodes.
	If result_key is None, the result dict is merged directly into the state.
	If result_key is provided, the result is wrapped under that key.
	If update_errors is False, errors are not updated (for parallel nodes).
	"""
	job_id = state.get("job_id", "unknown")
	logger.info("▶️ [NODE START] %s (job_id=%s)", node_name, job_id)
	
	for attempt in range(MAX_RETRIES):
		try:
			if attempt > 0:
				logger.warning("🔄 Retrying %s (attempt %d/%d)", node_name, attempt + 1, MAX_RETRIES)
			
			result = await func(state)
			
			if result_key is None:
				# Merge result directly
				output = {**result}
			else:
				# Wrap under result_key
				output = {result_key: result}
			
			# Only update errors if not a parallel node
			if update_errors:
				errors = dict(state.get("errors") or {})
				errors[node_name] = None
				output["errors"] = errors

			logger.info("✅ [NODE COMPLETE] %s (job_id=%s)", node_name, job_id)
			return output
		except Exception as exc:
			logger.error("❌ [NODE ERROR] %s (job_id=%s): %s", node_name, job_id, str(exc))
			if attempt < MAX_RETRIES - 1:
				wait_time = RETRY_DELAY_SECONDS * (attempt + 1)
				logger.warning("⏳ Retrying in %d seconds...", wait_time)
				await asyncio.sleep(wait_time)
			else:
				logger.error("💥 [NODE FAILED] %s failed after %d attempts (job_id=%s)", node_name, MAX_RETRIES, job_id)
				output = {}
				if result_key is None:
					# Return empty results for all expected keys
					output = {
						"title_result": None,
						"notes_result": None,
						"bom_result": None,
						"drawing_result": None,
					}
				else:
					output[result_key] = None

				if update_errors:
					errors = dict(state.get("errors") or {})
					errors[node_name] = str(exc)
					output["errors"] = errors

				return output
