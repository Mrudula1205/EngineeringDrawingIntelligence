from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

from models.schemas import ErrorResponse, UploadResponse
from pipeline.graph import build_graph
from services import firestore, gcs

router = APIRouter()

MAX_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
MAX_FILENAME_LENGTH = 200


logger = logging.getLogger(__name__)


async def _run_pipeline(job_id: str, gcs_path: str) -> None:
	logger.info("🚀 [PIPELINE START] job_id=%s, gcs_path=%s", job_id, gcs_path)
	graph = build_graph()
	state = {
		"pdf_gcs_path": gcs_path,
		"job_id": job_id,
		"drawing_id": str(uuid.uuid4()),
		"page_images": [],
		"raw_text_blocks": [],
		"raw_drawings": [],
		"bom_result": None,
		"notes_result": None,
		"title_result": None,
		"drawing_result": None,
		"errors": {},
		"final_json": None,
		"ingest_result": None,
		"store_result": None,
	}
	try:
		try:
			logger.debug("📋 Updating job status to 'processing'")
			firestore.update_job_status(job_id, "processing")
		except NotImplementedError:
			logger.warning("Firestore update_job_status not implemented.")
		logger.info("⏳ Starting graph execution...")
		result = await graph.ainvoke(state)
		logger.info("✅ [PIPELINE COMPLETE] job_id=%s, status=%s", job_id, result.get("final_json", {}).get("job_status", "unknown"))
	except Exception as exc:
		logger.exception("❌ [PIPELINE FAILED] job_id=%s: %s", job_id, str(exc))
		try:
			firestore.update_job_status(job_id, "failed")
		except NotImplementedError:
			logger.warning("Firestore update_job_status not implemented.")


@router.post(
	"",
	response_model=UploadResponse,
	status_code=status.HTTP_202_ACCEPTED,
	responses={
		400: {"model": ErrorResponse},
		413: {"model": ErrorResponse},
		415: {"model": ErrorResponse},
		501: {"model": ErrorResponse},
	},
)
async def upload_pdf(
	background_tasks: BackgroundTasks,
	file: UploadFile = File(...),
) -> UploadResponse:
	if not file.filename or not file.filename.lower().endswith(".pdf"):
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Only .pdf files are accepted.",
		)
	if len(file.filename) > MAX_FILENAME_LENGTH:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Filename exceeds maximum length.",
		)
	if any(part in file.filename for part in ("..", "/", "\\")):
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Invalid filename.",
		)
	if file.content_type not in ALLOWED_CONTENT_TYPES:
		raise HTTPException(
			status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
			detail="Unsupported content type.",
		)

	size = 0
	while True:
		chunk = await file.read(1024 * 1024)
		if not chunk:
			break
		size += len(chunk)
		if size > MAX_FILE_BYTES:
			raise HTTPException(
				status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
				detail="File exceeds size limit.",
			)

	await file.seek(0)
	logger.info("📤 File %s uploaded. Size: %.2f MB", file.filename, size / (1024 * 1024))

	job_id = str(uuid.uuid4())
	now = datetime.now(timezone.utc)
	job_payload = {
		"job_id": job_id,
		"status": "pending",
		"created_at": now.isoformat(),
	}

	try:
		logger.debug("💾 Creating job record in Firestore")
		firestore.create_job(job_id, job_payload)
		logger.debug("☁️ Uploading PDF to GCS")
		gcs_path = gcs.upload_pdf(file.file, f"{job_id}.pdf")
		logger.info("✅ File processed. job_id=%s, gcs_path=%s", job_id, gcs_path)
	except NotImplementedError as exc:
		logger.error("❌ Service not implemented: %s", str(exc))
		raise HTTPException(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			detail=str(exc),
		) from exc

	logger.info("📋 Queueing background task for pipeline execution (job_id=%s)", job_id)
	background_tasks.add_task(_run_pipeline, job_id, gcs_path)
	return UploadResponse(job_id=job_id, status="pending")
