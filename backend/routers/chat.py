from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from models.schemas import ChatRequest, ChatResponse, ErrorResponse
from services import firestore, gemini

router = APIRouter()

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_MESSAGE_LENGTH = 2000
MAX_HISTORY_TOTAL_CHARS = 10000


@router.post(
	"",
	response_model=ChatResponse,
	responses={
		400: {"model": ErrorResponse},
		404: {"model": ErrorResponse},
		501: {"model": ErrorResponse},
	},
)
def chat(request: ChatRequest) -> ChatResponse:
	if len(request.message) > MAX_MESSAGE_LENGTH:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Message exceeds maximum length.",
		)
	if len(request.history) > MAX_HISTORY_MESSAGES:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="History exceeds maximum message count.",
		)

	history_total = 0
	for msg in request.history:
		if len(msg.content) > MAX_HISTORY_MESSAGE_LENGTH:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="History message exceeds maximum length.",
			)
		history_total += len(msg.content)
	if history_total > MAX_HISTORY_TOTAL_CHARS:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="History content exceeds maximum total length.",
		)
	try:
		drawing = firestore.get_drawing_result(request.job_id)
	except NotImplementedError as exc:
		raise HTTPException(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			detail=str(exc),
		) from exc

	if not drawing:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Drawing not found.",
		)

	messages = [{"role": msg.role, "content": msg.content} for msg in request.history]
	context = json.dumps(drawing, ensure_ascii=True)
	messages.append(
		{
			"role": "user",
			"content": f"Drawing data: {context}\n\nQuestion: {request.message}",
		}
	)

	try:
		response_text = gemini.chat_with_drawing(messages)
	except NotImplementedError as exc:
		raise HTTPException(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			detail=str(exc),
		) from exc

	return ChatResponse(response=response_text)
