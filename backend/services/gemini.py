from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel, Part

logger = logging.getLogger(__name__)

_initialized = False


def _get_required_env(key: str) -> str:
	value = os.getenv(key)
	if not value:
		raise RuntimeError(f"Missing required environment variable: {key}")
	return value


def _init_vertex() -> None:
	global _initialized
	if _initialized:
		return
	project_id = _get_required_env("GOOGLE_CLOUD_PROJECT")
	location = os.getenv("VERTEX_LOCATION", "us-central1")
	vertexai.init(project=project_id, location=location)
	_initialized = True


def _parse_json_response(text: str) -> Dict[str, Any]:
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		start = text.find("{")
		end = text.rfind("}")
		if start >= 0 and end > start:
			return json.loads(text[start : end + 1])
		raise


def extract_drawing_dimensions(image_bytes: bytes, prompt: str) -> Dict[str, Any]:
	_init_vertex()

	model_name = os.getenv("GEMINI_DRAWING_MODEL", "gemini-2.0-flash")
	logger.debug("🤖 Initializing Gemini model: %s", model_name)
	model = GenerativeModel(model_name)
	image_part = Part.from_data(data=image_bytes, mime_type="image/png")

	logger.debug("📤 Sending image to Gemini API (size: %.2f MB)", len(image_bytes) / (1024 * 1024))
	response = model.generate_content(
		[prompt, image_part],
		generation_config=GenerationConfig(
			response_mime_type="application/json",
			temperature=0.2,
		),
	)

	logger.debug("✓ Received response from Gemini API")
	result = _parse_json_response(response.text)
	logger.debug("✓ Parsed JSON response successfully")
	return result


def extract_title_block(image_bytes: bytes, prompt: str) -> Dict[str, Any]:
	_init_vertex()

	model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash")
	model = GenerativeModel(model_name)
	image_part = Part.from_data(data=image_bytes, mime_type="image/png")

	response = model.generate_content(
		[prompt, image_part],
		generation_config=GenerationConfig(
			response_mime_type="application/json",
			temperature=0.2,
		),
	)

	return _parse_json_response(response.text)


def extract_notes(text: str, prompt: str) -> Dict[str, Any]:
	_init_vertex()

	model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash")
	model = GenerativeModel(model_name)

	response = model.generate_content(
		[f"{prompt}\n\nRAW NOTES:\n{text}"],
		generation_config=GenerationConfig(
			response_mime_type="application/json",
			temperature=0.1,
		),
	)

	return _parse_json_response(response.text)


def chat_with_drawing(messages: List[Dict[str, str]]) -> str:
	_init_vertex()

	model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash")
	model = GenerativeModel(model_name)

	lines = []
	for message in messages:
		role = message.get("role", "user").upper()
		content = message.get("content", "")
		lines.append(f"{role}: {content}")
	prompt = "\n".join(lines)

	response = model.generate_content(
		prompt,
		generation_config=GenerationConfig(temperature=0.2),
	)
	return response.text.strip()
