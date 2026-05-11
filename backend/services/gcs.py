from __future__ import annotations

import os
from typing import BinaryIO

from google.cloud import storage

_client: storage.Client | None = None


def _get_required_env(key: str) -> str:
	value = os.getenv(key)
	if not value:
		raise RuntimeError(f"Missing required environment variable: {key}")
	return value


def _get_client() -> storage.Client:
	global _client
	if _client is not None:
		return _client

	project_id = _get_required_env("GOOGLE_CLOUD_PROJECT")
	_client = storage.Client(project=project_id)
	return _client


def get_bucket_name() -> str:
	return _get_required_env("GCS_BUCKET_NAME")


def upload_pdf(file_obj: BinaryIO, destination_name: str) -> str:
	"""
	Uploads a PDF to GCS and returns the gs:// path.
	Implementation is intentionally deferred until credentials are configured.
	"""
	if not destination_name.lower().endswith(".pdf"):
		raise ValueError("destination_name must end with .pdf")
	if any(part in destination_name for part in ("..", "\\", "/")):
		raise ValueError("destination_name contains invalid characters")

	client = _get_client()
	bucket_name = get_bucket_name()
	bucket = client.bucket(bucket_name)
	blob = bucket.blob(destination_name)
	blob.upload_from_file(file_obj, content_type="application/pdf")
	return f"gs://{bucket_name}/{destination_name}"


def download_pdf(gcs_path: str) -> bytes:
	if not gcs_path.startswith("gs://"):
		raise ValueError("gcs_path must start with gs://")

	client = _get_client()
	path = gcs_path.replace("gs://", "", 1)
	bucket_name, _, blob_name = path.partition("/")
	if not bucket_name or not blob_name:
		raise ValueError("gcs_path must include bucket and object name")

	bucket = client.bucket(bucket_name)
	blob = bucket.blob(blob_name)
	return blob.download_as_bytes()
