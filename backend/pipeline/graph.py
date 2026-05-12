from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from pipeline.nodes import with_retry
from pipeline.nodes.extract_dimensions_vlm import extract_dimensions_vlm
from pipeline.nodes.extract_structured_data import (
	extract_structured_data,
	extract_notes,
	extract_tables_node as extract_tables_impl,
)
from pipeline.nodes.extract_title import extract_title
from pipeline.nodes.ingest import ingest_pdf
from pipeline.nodes.store_firestore import store_firestore
from pipeline.nodes.validate_merge import validate_merge
from pipeline.state import PipelineState


async def ingest_node(state: PipelineState) -> PipelineState:
	return await with_retry(ingest_pdf, state, "ingest", None)


async def extract_structured_data_node(state: PipelineState) -> PipelineState:
	return await with_retry(
		extract_structured_data, state, "structured_data", None, update_errors=False
	)


async def extract_notes_node(state: PipelineState) -> PipelineState:
	return await with_retry(extract_notes, state, "notes", None, update_errors=False)


async def extract_tables_node(state: PipelineState) -> PipelineState:
	return await with_retry(
		extract_tables_impl, state, "tables", None, update_errors=False
	)


async def extract_title_node(state: PipelineState) -> PipelineState:
	return await with_retry(extract_title, state, "title", None, update_errors=False)


async def extract_dimensions_vlm_node(state: PipelineState) -> PipelineState:
	return await with_retry(extract_dimensions_vlm, state, "dimensions_vlm", None, update_errors=False)


async def validate_merge_node(state: PipelineState) -> PipelineState:
	return await with_retry(validate_merge, state, "validate_merge", "final_json")


async def store_firestore_node(state: PipelineState) -> PipelineState:
	return await with_retry(store_firestore, state, "store_firestore", "store_result")


def build_graph() -> Any:
	graph = StateGraph(PipelineState)

	graph.add_node("ingest", ingest_node)
	graph.add_node("extract_structured_data", extract_structured_data_node)
	graph.add_node("extract_notes", extract_notes_node)
	graph.add_node("extract_title", extract_title_node)
	graph.add_node("extract_dimensions_vlm", extract_dimensions_vlm_node)
	graph.add_node("extract_tables", extract_tables_node)
	graph.add_node("validate_merge", validate_merge_node)
	graph.add_node("store_firestore", store_firestore_node)

	# Set entry point
	graph.set_entry_point("ingest")

	# After ingest, run all extractions in parallel (no region detection needed)
	graph.add_edge("ingest", "extract_structured_data")
	graph.add_edge("ingest", "extract_notes")
	graph.add_edge("ingest", "extract_title")
	graph.add_edge("ingest", "extract_dimensions_vlm")
	graph.add_edge("ingest", "extract_tables")

	# Merge results from all extractions
	graph.add_edge("extract_structured_data", "validate_merge")
	graph.add_edge("extract_notes", "validate_merge")
	graph.add_edge("extract_title", "validate_merge")
	graph.add_edge("extract_dimensions_vlm", "validate_merge")
	graph.add_edge("extract_tables", "validate_merge")

	# Final steps
	graph.add_edge("validate_merge", "store_firestore")
	graph.add_edge("store_firestore", END)

	return graph.compile()
