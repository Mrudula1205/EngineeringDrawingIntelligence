# DocIntelligence Backend

## Setup

1) Create a virtual environment and install dependencies from requirements.txt.
2) Copy .env.example to .env and set the required values.

## Run

```bash
uvicorn main:app --reload
```

## Agent State Graph

```mermaid
graph TD
  ingest[ingest] --> extract_structured[extract_structured_data]
  ingest --> extract_dims[extract_dimensions_vlm]
  extract_structured --> validate[validate_merge]
  extract_dims --> validate
  validate --> store[store_firestore]
  store --> end((END))
```

**Node Descriptions:**
- **ingest**: Loads PDF and extracts raw text blocks via Document AI
- **extract_structured_data** (parallel): Extracts title block, BOM, and notes from raw_text_blocks; falls back to OCR if empty
- **extract_dimensions_vlm** (parallel): Sends full PDF page image to Gemini VLM for spatial dimension understanding
- **validate_merge**: Combines results from both extraction branches; determines job status
- **store_firestore**: Persists final JSON and updates job status in Firestore
- API endpoints return 501 for unimplemented services.
