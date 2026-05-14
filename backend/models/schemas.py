from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


JobStatus = Literal["pending", "processing", "completed", "partial", "failed"]
UnitSystem = Literal["mm", "in"]
MaterialSource = Literal["notes", "title_block", "null"]


class UploadResponse(BaseModel):
	job_id: str
	status: JobStatus


class JobStatusResponse(BaseModel):
	job_id: str
	status: JobStatus
	processed_at: Optional[datetime] = None


class ChatMessage(BaseModel):
	role: Literal["user", "assistant"]
	content: str


class ChatRequest(BaseModel):
	job_id: str
	message: str
	history: List[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
	response: str


class DimensionValue(BaseModel):
	"""Represents a single dimension value extracted from a drawing."""
	value: Optional[float] = None
	unit: Optional[str] = None
	confidence: float = 0.0


# Views contain arbitrary named dimensions; map view name -> (dimension name -> DimensionValue)
from typing import Dict as _Dict
ViewDimensions = _Dict[str, DimensionValue]


class DimensionsBlock(BaseModel):
	views: Dict[str, ViewDimensions] = Field(default_factory=dict)
	extraction_notes: Optional[str] = None
	extraction_error: Optional[str] = None


class TitleBlock(BaseModel):
	drawing_number: Optional[str] = None
	title: Optional[str] = None
	company: Optional[str] = None
	revision: Optional[str] = None
	date: Optional[str] = None
	scale: Optional[str] = None
	sheet: Optional[str] = None
	material: Optional[str] = None
	drawn_by: Optional[str] = None
	additional_fields: Dict[str, str] = Field(default_factory=dict)
	fields_present: List[str] = Field(default_factory=list)
	extraction_error: Optional[str] = None


class BomRow(BaseModel):
    item: Optional[str] = None
    part_number: Optional[str] = None
    sap_no: Optional[str] = None
    code: Optional[str] = None
    code2: Optional[str] = None
    description: Optional[str] = None
    description2: Optional[str] = None
    quantity: Optional[str] = None
    rev: Optional[str] = None
    vendor: Optional[str] = None
    vendor2: Optional[str] = None
    weight: Optional[str] = None


class BomBlock(BaseModel):
    rows: List[BomRow] = Field(default_factory=list)
    headers: List[str] = Field(default_factory=list)
    extraction_error: Optional[str] = None


class NotesBlock(BaseModel):
	material: Optional[str] = None
	material_standard: Optional[str] = None
	dimensional_notes: List[str] = Field(default_factory=list)
	surface_finish_notes: List[str] = Field(default_factory=list)
	process_notes: List[str] = Field(default_factory=list)
	general_notes: List[str] = Field(default_factory=list)
	raw_text: Optional[str] = None
	extraction_error: Optional[str] = None


class ExtractionSummary(BaseModel):
	null_fields: List[str] = Field(default_factory=list)
	min_confidence_score: float = 1.0


class DrawingDocument(BaseModel):
	drawing_id: str
	job_id: str
	job_status: JobStatus
	processed_at: Optional[datetime] = None
	source_gcs_path: str
	unit_original: UnitSystem
	unit_normalized: Literal["mm"] = "mm"
	title_block: TitleBlock = Field(default_factory=TitleBlock)
	bom: BomBlock = Field(default_factory=BomBlock)
	notes: NotesBlock = Field(default_factory=NotesBlock)
	dimensions: DimensionsBlock = Field(default_factory=DimensionsBlock)
	material_resolved: Optional[str] = None
	material_source: MaterialSource = "null"
	extraction_summary: ExtractionSummary = Field(default_factory=ExtractionSummary)


class JobResultResponse(BaseModel):
	result: DrawingDocument


class ErrorDetail(BaseModel):
	message: str
	code: int
	request_id: Optional[str] = None
	details: Optional[List[Dict[str, str]]] = None


class ErrorResponse(BaseModel):
	error: ErrorDetail
