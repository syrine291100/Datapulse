"""API d'import transactionnel et consultation des ventes."""

import os
import secrets
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated
from fastapi import Depends, FastAPI, Header, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.database import Base, Batch, Sale, Session, engine
from backend.pipeline import MAX_BYTES, parse_csv


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="DataPulse API", version="1.0.0", lifespan=lifespan)


def get_session():
    with Session() as session:
        yield session


def authorize(x_api_key: Annotated[str | None, Header()] = None):
    key = os.getenv("IMPORT_API_KEY", "")
    if len(key) < 32:
        raise HTTPException(503, "Configurer IMPORT_API_KEY avec au moins 32 caractères.")
    if not secrets.compare_digest(x_api_key or "", key):
        raise HTTPException(401, "Clé d’import incorrecte.")


def validated(data):
    try:
        return parse_csv(data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/imports/preview", dependencies=[Depends(authorize)])
def preview(file: UploadFile):
    rows, errors = validated(file.file.read(MAX_BYTES + 1))
    return {
        "valid_rows": len(rows),
        "invalid_rows": len(errors),
        "errors": errors,
        "preview": [{**r, "unit_price": str(r["unit_price"])} for r in rows[:10]],
    }


@app.post("/imports", status_code=201, dependencies=[Depends(authorize)])
def import_sales(file: UploadFile, session=Depends(get_session)):
    rows, errors = validated(file.file.read(MAX_BYTES + 1))
    if errors:
        raise HTTPException(422, {"message": "Import refusé : corriger toutes les lignes.", "errors": errors})
    existing = set(session.scalars(select(Sale.sale_id)).all())
    duplicates = [r["sale_id"] for r in rows if r["sale_id"] in existing]
    if duplicates:
        raise HTTPException(
            409, {"message": "Identifiants déjà importés. Aucune ligne ajoutée.", "sale_ids": duplicates}
        )
    batch = Batch(filename=(file.filename or "ventes.csv")[:120], row_count=len(rows))
    session.add(batch)
    session.flush()
    session.add_all([Sale(**r, batch_id=batch.id) for r in rows])
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Conflit avec un autre import. Aucune ligne ajoutée.") from exc
    return {"batch_id": batch.id, "imported_rows": len(rows)}


@app.get("/sales")
def sales(
    start: date | None = None,
    end: date | None = None,
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50000)] = 50000,
    session=Depends(get_session),
):
    if start and end and start > end:
        raise HTTPException(422, "La date de début doit précéder la date de fin.")
    query = select(Sale).order_by(Sale.date, Sale.sale_id)
    if start:
        query = query.where(Sale.date >= start)
    if end:
        query = query.where(Sale.date <= end)
    if category:
        query = query.where(Sale.category == category)
    return [
        {
            "sale_id": r.sale_id,
            "date": r.date.isoformat(),
            "product": r.product,
            "category": r.category,
            "quantity": r.quantity,
            "unit_price": str(r.unit_price),
            "revenue": str(r.unit_price * r.quantity),
        }
        for r in session.scalars(query.limit(limit))
    ]


@app.get("/imports")
def batches(session=Depends(get_session)):
    return [
        {"id": r.id, "filename": r.filename, "created_at": r.created_at.isoformat(), "row_count": r.row_count}
        for r in session.scalars(select(Batch).order_by(Batch.id.desc()).limit(100))
    ]
