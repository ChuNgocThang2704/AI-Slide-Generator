import sys
# Configure console encoding to UTF-8 to prevent charmap/UnicodeEncodeError on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from routes.api import router as api_router



def create_app() -> FastAPI:
    app = FastAPI(title="AI Slide Generator API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    base_dir = Path(__file__).resolve().parent.parent
    output_dir = base_dir / "outputs"
    output_dir.mkdir(exist_ok=True)

    app.mount("/outputs", StaticFiles(directory=str(output_dir)), name="outputs")
    ui_dir = base_dir / "frontend" / "public"
    if ui_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")
    else:
        print("[main] Warning: frontend/public directory not found, skipping UI mount.")

    app.include_router(api_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
