import json
import os

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import ValidationError

from app import storage
from app.detectors.engine import analyze_trace
from app.schemas.trace import Trace

router = APIRouter(prefix="/api/traces", tags=["traces"])
MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "1000000"))


@router.post("", status_code=201)
async def upload_trace(file: UploadFile = File(...)):
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_BYTES} bytes")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(400, f"Invalid JSON: {e}")
    try:
        trace = Trace.model_validate(data)
    except ValidationError as e:
        raise HTTPException(422, detail=json.loads(e.json(include_url=False)))
    storage.save_trace(trace)
    return {"id": trace.run_id, "event_count": len(trace.events)}


@router.get("/{run_id}")
def read_trace(run_id: str):
    trace = storage.get_trace(run_id)
    if trace is None:
        raise HTTPException(404, "Trace not found")
    return trace


@router.post("/{run_id}/analyze")
def analyze(run_id: str):
    trace = storage.get_trace(run_id)
    if trace is None:
        raise HTTPException(404, "Trace not found")
    result = analyze_trace(trace)
    storage.save_findings(run_id, result)
    return result


@router.get("/{run_id}/findings")
def read_findings(run_id: str):
    result = storage.get_findings(run_id)
    if result is None:
        raise HTTPException(404, "No analysis for this trace yet; call POST /api/traces/{id}/analyze")
    return result
