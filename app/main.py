import os
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.enums import AppMessage
from app.core.auth_gate import AuthGateMiddleware
from app.services.github_service import github_service
from app.services.db_service import db_service
from app.api.routes import router as api_router
from app.api.auth import router as auth_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("cto-copilot")

app = FastAPI(
    title="CTO Copilot API",
    description="Automated GitHub PR monitoring, analysis, and AI summarization for CTO command centers.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthGateMiddleware)

app.include_router(api_router)
app.include_router(auth_router)

static_path = os.path.join(os.getcwd(), settings.static_dir)
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(static_path, "index.html"))

    @app.get("/login")
    async def serve_login():
        login_path = os.path.join(static_path, "login.html")
        if os.path.exists(login_path):
            return FileResponse(login_path)
        return FileResponse(os.path.join(static_path, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(static_path, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(static_path, "index.html"))

async def auto_poll_prs():
    """Periodic GitHub poller for repository updates."""
    while True:
        try:
            await asyncio.sleep(settings.github_poll_interval_seconds)
            await github_service.get_pull_requests(state="all")
        except Exception as e:
            logger.warning(f"Background PR poll failed: {e}")

@app.on_event("startup")
async def startup_event():
    logger.info(AppMessage.STARTUP.value)
    await db_service.init_db()
    asyncio.create_task(auto_poll_prs())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)

