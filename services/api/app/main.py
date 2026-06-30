"""Точка входа FastAPI-сервиса."""

from fastapi import FastAPI

from app import __version__
from app.api import router

app = FastAPI(title="KateSearches API", version=__version__)
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}
