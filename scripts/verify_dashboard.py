import os
import subprocess
import time
import tempfile
import sys
from pathlib import Path
import requests
from streamlit.testing.v1 import AppTest

root = Path(__file__).resolve().parents[1]
os.chdir(root)
os.environ["IMPORT_API_KEY"] = "datapulse-smoke-test-secret-at-least-32"
os.environ["API_URL"] = "http://127.0.0.1:8091"
with tempfile.TemporaryDirectory() as temp:
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(temp) / "test.db")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8091"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                if requests.get(os.environ["API_URL"] + "/health", timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.1)
        at = AppTest.from_file(str(root / "frontend/app.py"), default_timeout=20).run()
        assert not at.exception and at.info
        r = requests.post(
            os.environ["API_URL"] + "/imports",
            files={"file": ("sales_demo.csv", (root / "data/sales_demo.csv").read_bytes(), "text/csv")},
            headers={"X-API-Key": os.environ["IMPORT_API_KEY"]},
            timeout=10,
        )
        assert r.status_code == 201, r.text
        at.run()
        assert not at.exception, list(at.exception)
        assert len(at.metric) == 3
        assert at.metric[1].value == "180"
        at.multiselect[0].set_value(["Boissons"]).run()
        assert not at.exception and int(at.metric[1].value) < 180
        at.sidebar.radio[0].set_value("Historique").run()
        assert not at.exception and len(at.dataframe) == 1
        at.sidebar.radio[0].set_value("Importer des ventes").run()
        assert not at.exception
        print("Dashboard smoke passed: empty state, import, KPIs, filters, history, upload screen")
    finally:
        process.terminate()
        process.wait()
