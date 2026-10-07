import os

os.environ["IMPORT_API_KEY"] = "a-test-key-with-more-than-32-characters"
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from backend.database import Base
from backend.main import app, get_session
from backend.pipeline import COLUMNS, MAX_BYTES, parse_csv

HEADER = ",".join(COLUMNS) + "\n"
GOOD = "s1,2026-01-01,Café,Boissons,2,3.50\n"
AUTH = {"X-API-Key": os.environ["IMPORT_API_KEY"]}


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)

    def dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = dependency
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()


def send(client, text, route="/imports", auth=AUTH):
    return client.post(route, files={"file": ("test.csv", text.encode(), "text/csv")}, headers=auth)


def test_import_exact_money_and_history(client):
    assert send(client, HEADER + GOOD).status_code == 201
    sale = client.get("/sales").json()[0]
    assert sale["revenue"] == "7.00"
    assert client.get("/imports").json()[0]["row_count"] == 1


def test_invalid_row_rolls_back_entire_file(client):
    result = send(client, HEADER + GOOD + "s2,bad,Thé,Boissons,-1,NaN\n")
    assert result.status_code == 422
    assert result.json()["detail"]["errors"][0]["line"] == 3
    assert client.get("/sales").json() == []
    assert client.get("/imports").json() == []


def test_reimport_no_duplicates_or_partial_insert(client):
    assert send(client, HEADER + GOOD).status_code == 201
    assert send(client, HEADER + GOOD + "s2,2026-01-02,Thé,Boissons,1,2.00\n").status_code == 409
    assert len(client.get("/sales").json()) == 1
    assert len(client.get("/imports").json()) == 1


def test_preview_does_not_write_and_detects_duplicate(client):
    result = send(client, HEADER + GOOD + GOOD, "/imports/preview").json()
    assert result["invalid_rows"] == 1
    assert "doublon" in result["errors"][0]["reason"]
    assert client.get("/sales").json() == []


def test_unauthorized_import(client):
    assert send(client, HEADER + GOOD, auth={}).status_code == 401
    assert send(client, HEADER + GOOD, auth={"X-API-Key": "bad"}).status_code == 401


def test_filters_and_date_validation(client):
    assert send(client, HEADER + GOOD + "s2,2026-01-02,Tasse,Accessoires,1,9.99\n").status_code == 201
    assert len(client.get("/sales?category=Boissons").json()) == 1
    assert client.get("/sales?start=2026-02-01").json() == []
    assert client.get("/sales?start=2026-02-01&end=2026-01-01").status_code == 422


@pytest.mark.parametrize(
    "row",
    [
        "s1,2026-01-01,Café,Boissons,1.5,3.50\n",
        "s1,2026-01-01,Café,Boissons,2,1.234\n",
        "s1,2026-01-01,,Boissons,2,3.50\n",
        "s1,2026-01-01,Café,Boissons,2,Infinity\n",
        "s1,2026-02-30,Café,Boissons,2,3.50\n",
    ],
)
def test_invalid_values(row):
    valid, errors = parse_csv((HEADER + row).encode())
    assert not valid and errors


@pytest.mark.parametrize(
    "data",
    [b"", b"wrong,header\n", b"\xff", b"x" * (MAX_BYTES + 1)],
    ids=["empty", "wrong-header", "invalid-encoding", "too-large"],
)
def test_invalid_file(data):
    with pytest.raises(ValueError):
        parse_csv(data)
