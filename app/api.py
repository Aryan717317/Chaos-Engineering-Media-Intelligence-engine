"""Read-only analysis endpoints for the media graph."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.models import NetworkResponse
from app.queries import AmbiguousEntity, network
from app.storage import initialize


def create_app(database: str | None = None) -> FastAPI:
    database = database or os.getenv("MEDIA_DB_PATH", "data/graph.db")

    @asynccontextmanager
    async def lifespan(application):
        initialize(database)
        yield

    application = FastAPI(title="Media intelligence graph", version="0.1.0", lifespan=lifespan)

    @application.get("/entity/{name}/network", response_model=NetworkResponse)
    def entity_network(name: str, depth: int = Query(default=2, ge=1, le=2), include_weak: bool = True):
        try:
            return network(database, name, depth, include_weak)
        except KeyError:
            raise HTTPException(status_code=404, detail="Entity not found") from None
        except AmbiguousEntity as exc:
            raise HTTPException(status_code=409, detail={"message": str(exc),
                "candidates": [node.model_dump(mode="json") for node in exc.candidates]}) from exc

    return application


app = create_app()
