from __future__ import annotations

import os
from typing import Any, Dict, Optional

from google.cloud import firestore

_client: Optional[firestore.Client] = None


def _get_required_env(key: str) -> str:
	value = os.getenv(key)
	if not value:
		raise RuntimeError(f"Missing required environment variable: {key}")
	return value


def _get_client() -> firestore.Client:
	global _client
	if _client is not None:
		return _client

	project_id = _get_required_env("GOOGLE_CLOUD_PROJECT")
	_client = firestore.Client(project=project_id)
	return _client


def get_collection_names() -> tuple[str, str]:
	drawings = _get_required_env("FIRESTORE_COLLECTION_DRAWINGS")
	jobs = _get_required_env("FIRESTORE_COLLECTION_JOBS")
	return drawings, jobs


def create_job(job_id: str, payload: Dict[str, Any]) -> None:
	if not job_id:
		raise ValueError("job_id is required")

	client = _get_client()
	_, jobs_collection = get_collection_names()
	client.collection(jobs_collection).document(job_id).set(payload)


def update_job_status(job_id: str, status: str) -> None:
	if not job_id:
		raise ValueError("job_id is required")

	client = _get_client()
	_, jobs_collection = get_collection_names()
	client.collection(jobs_collection).document(job_id).set(
		{"status": status},
		merge=True,
	)


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
	if not job_id:
		raise ValueError("job_id is required")

	client = _get_client()
	_, jobs_collection = get_collection_names()
	snapshot = client.collection(jobs_collection).document(job_id).get()
	if not snapshot.exists:
		return None
	return snapshot.to_dict()


def get_drawing_result(job_id: str) -> Optional[Dict[str, Any]]:
	if not job_id:
		raise ValueError("job_id is required")

	client = _get_client()
	drawings_collection, _ = get_collection_names()
	query = (
		client.collection(drawings_collection)
		.where(field_path="job_id", op_string="==", value=job_id)
		.limit(1)
	)
	results = list(query.stream())
	if not results:
		return None
	return results[0].to_dict()


def list_drawings() -> list[Dict[str, Any]]:
	client = _get_client()
	drawings_collection, _ = get_collection_names()
	return [doc.to_dict() for doc in client.collection(drawings_collection).stream()]


def store_drawing(drawing_id: str, payload: Dict[str, Any]) -> None:
	if not drawing_id:
		raise ValueError("drawing_id is required")

	client = _get_client()
	drawings_collection, _ = get_collection_names()
	client.collection(drawings_collection).document(drawing_id).set(payload)
