from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from models.schemas import DrawingDocument, ErrorResponse, JobResultResponse, JobStatusResponse
from services import firestore

router = APIRouter()


def _validate_job_id(job_id: str) -> None:
	try:
		uuid.UUID(job_id)
	except ValueError as exc:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Invalid job_id format.",
		) from exc


def _sanitize_dimensions(result: dict) -> dict:
	"""
	Clean up dimension and title block data to ensure it conforms to the schema.
	- Remove None values from title_block.additional_fields (only keep non-null values)
	- Validate all dimension keys have numeric values and valid confidence
	- Skip dimensions with non-numeric values (e.g., thread specs)
	- Promote old `other_dimensions` entries into top-level named keys
	"""
	# Sanitize title_block.additional_fields - remove None values
	if "title_block" in result and isinstance(result["title_block"], dict):
		additional_fields = result["title_block"].get("additional_fields", {})
		if isinstance(additional_fields, dict):
			# Keep only non-None values
			result["title_block"]["additional_fields"] = {
				k: v for k, v in additional_fields.items() if v is not None
			}
	
	# Sanitize dimensions (now with dynamic keys, not hardcoded fields)
	if "dimensions" not in result or "views" not in result.get("dimensions", {}):
		return result
	
	views = result["dimensions"]["views"]
	for view_name, view_data in views.items():
		if not isinstance(view_data, dict):
			continue
		
		# Validate all existing dimension keys (dynamic schema)
		# Skip any with non-numeric values, keep only valid numeric dimensions
		for key, dim_obj in list(view_data.items()):
			if key == "other_dimensions":
				# We'll handle below
				continue
			if isinstance(dim_obj, dict):
				# Validate that value is numeric (or None)
				val = dim_obj.get("value")
				if val is not None:
					try:
						dim_obj["value"] = float(val)
					except (TypeError, ValueError):
						# Non-numeric value; skip this dimension entirely
						view_data.pop(key, None)
						continue
				
				# Ensure confidence is numeric
				if dim_obj.get("confidence") is None:
					dim_obj["confidence"] = 0.0
				else:
					try:
						dim_obj["confidence"] = float(dim_obj["confidence"])
					except (TypeError, ValueError):
						dim_obj["confidence"] = 0.0
		
		# Backward-compat: Promote old `other_dimensions` list into named top-level keys
		if "other_dimensions" in view_data:
			for dim in view_data.get("other_dimensions", []):
				if not isinstance(dim, dict):
					continue
				
				name = dim.get("name")
				if not name:
					# skip unnamed entries
					continue
				
				# Normalize name to a safe key (strip/replace unsafe chars)
				key_name = str(name).strip()
				
				# Ensure numeric value is actually a number
				try:
					value = dim.get("value")
					if value is not None:
						value = float(value)
				except (TypeError, ValueError):
					# skip invalid numeric values
					continue
				
				# Ensure confidence is numeric
				conf = dim.get("confidence")
				if conf is None:
					conf = 0.0
				else:
					try:
						conf = float(conf)
					except (TypeError, ValueError):
						conf = 0.0
				
				unit = dim.get("unit") if dim.get("unit") is not None else None
				
				# Assign promoted dimension (overwrite only if absent)
				if key_name not in view_data:
					view_data[key_name] = {
						"value": value,
						"unit": unit,
						"confidence": conf,
					}
			
			# remove legacy list to favor the promoted keys
			view_data.pop("other_dimensions", None)
	
	return result


@router.get(
	"/{job_id}/status",
	response_model=JobStatusResponse,
	responses={
		400: {"model": ErrorResponse},
		404: {"model": ErrorResponse},
		501: {"model": ErrorResponse},
	},
)
def job_status(job_id: str) -> JobStatusResponse:
	_validate_job_id(job_id)
	try:
		result = firestore.get_job_status(job_id)
	except NotImplementedError as exc:
		raise HTTPException(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			detail=str(exc),
		) from exc

	if not result:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Job not found.",
		)

	return JobStatusResponse(
		job_id=job_id,
		status=result.get("status", "pending"),
		processed_at=result.get("processed_at"),
	)


@router.get(
	"/{job_id}/result",
	response_model=JobResultResponse,
	responses={
		400: {"model": ErrorResponse},
		404: {"model": ErrorResponse},
		501: {"model": ErrorResponse},
	},
)
def job_result(job_id: str) -> JobResultResponse:
	_validate_job_id(job_id)
	try:
		result = firestore.get_drawing_result(job_id)
	except NotImplementedError as exc:
		raise HTTPException(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			detail=str(exc),
		) from exc

	if not result:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Result not found.",
		)

	# Sanitize dimension data before validation
	result = _sanitize_dimensions(result)
	
	return JobResultResponse(result=DrawingDocument(**result))
