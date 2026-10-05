"""Lecture script for an uploaded deck: write it, rewrite it on request, export it to Excel.

A feature of its own: it reads a finished deck and never goes through slide generation.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

import routes.api as core
from services.lecture_script import MAX_SLIDES, estimated_minutes, read_deck, tidy_script, word_count, write_script
from services.lecture_script_xlsx import build_workbook

router = APIRouter(prefix="/api/lecture-script")

_MAX_FILE_BYTES = 80 * 1024 * 1024
_running: set = set()   # keeps the background tasks referenced until they finish


class ScriptRow(BaseModel):
    scene: str = ""
    slide: Optional[int] = None
    script: str = ""
    note: str = ""


class ReviseRequest(BaseModel):
    slides: List[Dict[str, Any]] = Field(default_factory=list)
    rows: List[ScriptRow] = Field(default_factory=list)
    prompt: str = ""
    filename: str = ""


class ExportRequest(BaseModel):
    title: str = ""
    sheet: str = ""
    duration_minutes: Optional[int] = None
    rows: List[ScriptRow] = Field(default_factory=list)


def _start(task_id: str, slides: List[Dict[str, Any]], prompt: str, filename: str, previous_rows=None) -> None:
    async def run() -> None:
        queue = core.redis_queue

        async def progress(value: int) -> None:
            await queue.update_task_status(task_id, "processing", progress=value)

        try:
            await progress(8)
            extractor = core._new_task_content_extractor(task_id)
            script = await write_script(
                extractor, slides, prompt=prompt, filename=filename,
                previous_rows=previous_rows, on_progress=progress,
            )
            await queue.update_task_status(task_id, "completed", progress=100, result={"script": script, "slides": slides})
        except Exception as error:
            print(f"[lecture_script] task {task_id} failed: {error!r}")
            message = str(error) if isinstance(error, (RuntimeError, ValueError)) else "Không tạo được kịch bản. Hãy thử lại."
            await queue.update_task_status(task_id, "error", progress=0, result={"message": message})

    task = asyncio.create_task(run())
    _running.add(task)
    task.add_done_callback(_running.discard)


@router.post("/generate")
async def generate(file: UploadFile = File(...), prompt: str = Form("")):
    """Read the deck and start writing its script; poll /api/status/{task_id} for the result."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File rỗng")
    if len(data) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File quá lớn (tối đa 80MB)")
    try:
        slides = await asyncio.to_thread(read_deck, data, file.filename or "")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        print(f"[lecture_script] cannot read {file.filename!r}: {error!r}")
        raise HTTPException(status_code=400, detail="Không đọc được file. Hãy dùng file .pptx hoặc .pdf không bị khoá.")
    task_id = str(uuid.uuid4())
    await core.redis_queue.update_task_status(task_id, "processing", progress=3)
    _start(task_id, slides, prompt, file.filename or "")
    return {"task_id": task_id, "slide_count": len(slides)}


@router.post("/revise")
async def revise(request: ReviseRequest):
    """Rewrite a script the user is looking at so it follows `prompt`."""
    if not request.slides or len(request.slides) > MAX_SLIDES:
        raise HTTPException(status_code=400, detail="Thiếu nội dung slide của kịch bản")
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Hãy mô tả điều bạn muốn chỉnh")
    slides = [
        {
            "number": int(slide.get("number") or index + 1), "title": str(slide.get("title") or "")[:200],
            "text": str(slide.get("text") or "")[:1400], "notes": str(slide.get("notes") or "")[:600],
            "has_figure": bool(slide.get("has_figure")),
        }
        for index, slide in enumerate(request.slides) if isinstance(slide, dict)
    ]
    task_id = str(uuid.uuid4())
    await core.redis_queue.update_task_status(task_id, "processing", progress=3)
    _start(task_id, slides, request.prompt, request.filename, [row.model_dump() for row in request.rows])
    return {"task_id": task_id, "slide_count": len(slides)}


@router.post("/export")
async def export(request: ExportRequest):
    """The script the user approved, as an .xlsx in the layout of a production script."""
    rows = [
        {"scene": row.scene.strip()[:60], "script": tidy_script(row.script), "note": row.note.strip()[:200]}
        for row in request.rows if row.scene.strip() or row.script.strip()
    ]
    if not rows:
        raise HTTPException(status_code=400, detail="Kịch bản trống")
    minutes = request.duration_minutes or estimated_minutes(rows)
    data = await asyncio.to_thread(build_workbook, {
        "title": request.title.strip()[:200], "sheet": request.sheet.strip(), "duration_minutes": minutes, "rows": rows,
    })
    name = quote((request.title.strip() or "Kich ban dung")[:80] + ".xlsx")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{name}",
            "X-Script-Words": str(sum(word_count(row["script"]) for row in rows)),
        },
    )
