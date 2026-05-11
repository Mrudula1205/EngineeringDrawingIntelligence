import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from config import load_env, setup_logging
from routers import chat, excel, jobs, upload

load_env()
setup_logging()

app = FastAPI(title="DocIntelligence API", version="0.1.0")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": str(exc.detail),
                "code": exc.status_code,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": "Validation error.",
                "code": 422,
                "request_id": request_id,
                "details": [
                    {"loc": "/".join(str(item) for item in err.get("loc", [])), "msg": err.get("msg", "")}
                    for err in exc.errors()
                ],
            }
        },
    )

app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(jobs.router, prefix="/job", tags=["jobs"])
app.include_router(excel.router, prefix="/excel", tags=["excel"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
