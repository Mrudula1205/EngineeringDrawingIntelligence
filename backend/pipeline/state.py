from typing import Annotated, Any, Optional, TypedDict


def merge_dicts(left: Optional[dict], right: Optional[dict]) -> Optional[dict]:
    """Custom reducer for merging dict values, handling None gracefully."""
    if left is None and right is None:
        return {}
    if left is None:
        return right if right is not None else {}
    if right is None:
        return left
    return left | right


class PipelineState(TypedDict):
    pdf_gcs_path: str
    job_id: str
    drawing_id: str
    page_images: list[bytes]
    raw_text_blocks: list[dict]
    bom_result: Annotated[Optional[dict], merge_dicts]
    notes_result: Annotated[Optional[dict], merge_dicts]
    title_result: Annotated[Optional[dict], merge_dicts]
    drawing_result: Annotated[Optional[dict], merge_dicts]
    errors: Annotated[dict, merge_dicts]
    final_json: Optional[dict]
    ingest_result: Optional[dict]
    store_result: Optional[dict]
