"""Запустить локальное приложение с отдельными расчётом, хранением и интерфейсом."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app.logging import setup_logging
from app.storage import Repository
from app.web import configure_http, create_router


def create_app(
    database_path: Path | None = None, frontend_path: Path | None = None
) -> FastAPI:
    """Создать приложение; тесты передают отдельную временную базу.

    Args:
        database_path: Путь к SQLite; по умолчанию var/komplekt.sqlite3.
        frontend_path: Готовая сборка интерфейса для локального запуска.

    Returns:
        FastAPI с ограниченным вводом и локальным постоянным хранилищем.
    """
    setup_logging()
    root = Path(__file__).resolve().parent.parent
    data_dir = Path(os.environ.get("KOMPLEKT_DATA_DIR", str(root / "var")))
    repository = Repository(database_path or data_dir / "komplekt.sqlite3")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        repository.initialize()
        yield

    app = FastAPI(
        title="Комплект",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    configure_http(app)
    app.include_router(create_router(repository, root / "data"))
    frontend = frontend_path or root / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="interface")
    return app
