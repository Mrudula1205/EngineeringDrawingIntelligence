from __future__ import annotations

from typing import List, Tuple


def page_size_from_blocks(blocks: List[dict], page_index: int) -> Tuple[float, float]:
    max_x = 0.0
    max_y = 0.0
    for block in blocks:
        if block.get("page") != page_index:
            continue
        bbox = block.get("bbox") or []
        if len(bbox) == 4:
            max_x = max(max_x, float(bbox[2]))
            max_y = max(max_y, float(bbox[3]))
    return max_x, max_y


def scale_bbox_to_image(
    bbox: Tuple[float, float, float, float],
    page_size: Tuple[float, float],
    image_size: Tuple[int, int],
) -> Tuple[float, float, float, float]:
    page_width, page_height = page_size
    image_width, image_height = image_size
    if page_width <= 0 or page_height <= 0:
        return bbox

    scale_x = image_width / page_width
    scale_y = image_height / page_height
    x0, y0, x1, y1 = bbox
    return (x0 * scale_x, y0 * scale_y, x1 * scale_x, y1 * scale_y)


def extract_text_in_bbox(
    blocks: List[dict],
    bbox: Tuple[float, float, float, float],
    page_index: int,
) -> str:
    left, top, right, bottom = bbox
    parts: List[str] = []
    for block in blocks:
        if block.get("page") != page_index:
            continue
        block_bbox = block.get("bbox") or []
        if len(block_bbox) != 4:
            continue
        x0, y0, x1, y1 = block_bbox
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        if left <= cx <= right and top <= cy <= bottom:
            text = (block.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts)
