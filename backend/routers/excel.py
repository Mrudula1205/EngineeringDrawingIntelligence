from __future__ import annotations

import io
import os

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from models.schemas import ErrorResponse
from services import firestore
from utils.excel_utils import generate_excel_from_firestore

router = APIRouter()


@router.get(
	"/download",
	responses={
		501: {"model": ErrorResponse},
	},
)
def download_excel() -> StreamingResponse:
	try:
		drawings = firestore.list_drawings()
		excel_bytes = generate_excel_from_firestore(drawings)
	except NotImplementedError as exc:
		raise HTTPException(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			detail=str(exc),
		) from exc

	file_name = os.getenv("EXCEL_FILE_NAME", "drawings_extraction.xlsx")
	stream = io.BytesIO(excel_bytes)
	response = StreamingResponse(
		stream,
		media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	)
	response.headers["Content-Disposition"] = f"attachment; filename={file_name}"
	return response
