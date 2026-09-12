"""Read-only analysis endpoints for the media graph."""

import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query

from app.models import CentralityResponse, ConnectionsResponse, NetworkResponse, utc_time
from app.queries import AmbiguousEntity, central_entities, emerging_connections, network
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

    @application.get("/connections/new", response_model=ConnectionsResponse)
    def new_connections(since: str = Query(...), include_weak: bool = True):
        try:
            boundary = utc_time(datetime.fromisoformat(since.replace("Z", "+00:00")))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="since must be an ISO timestamp with a timezone") from exc
        return emerging_connections(database, boundary, include_weak)

    @application.get("/entities/central", response_model=CentralityResponse)
    def central(limit: int = Query(default=20, ge=1, le=100), include_weak: bool = True):
        return central_entities(database, limit, include_weak)

    return application


app = create_app()
