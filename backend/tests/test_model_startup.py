import logging
import threading
import time

from fastapi.testclient import TestClient

from app import main
from app.ml import analyzer


def test_server_siap_tanpa_menunggu_model(monkeypatch):
    release = threading.Event()
    started = threading.Event()

    def slow_load():
        started.set()
        release.wait(timeout=20)

    monkeypatch.setattr(main, "get_analyzer", slow_load)
    begin = time.monotonic()
    with TestClient(main.app) as client:
        assert time.monotonic() - begin < 5
        assert started.wait(timeout=5)
        assert client.get("/docs").status_code == 200
        assert main.app.state.model_loader.is_alive()
        release.set()
        main.app.state.model_loader.join(timeout=5)
        assert not main.app.state.model_loader.is_alive()


def test_model_belum_terpasang_dicatat_dan_server_tetap_jalan(monkeypatch, caplog):
    def missing():
        raise analyzer.ModelNotInstalled("Model tidak ditemukan.")

    monkeypatch.setattr(main, "get_analyzer", missing)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        with TestClient(main.app) as client:
            main.app.state.model_loader.join(timeout=5)
            assert client.get("/docs").status_code == 200
    assert any("Model tidak ditemukan" in r.getMessage() for r in caplog.records)


def test_galat_lain_saat_memuat_dicatat_tanpa_menjatuhkan_server(monkeypatch, caplog):
    def broken():
        raise RuntimeError("rusak")

    monkeypatch.setattr(main, "get_analyzer", broken)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        with TestClient(main.app) as client:
            main.app.state.model_loader.join(timeout=5)
            assert client.get("/docs").status_code == 200
    assert any("RuntimeError" in r.getMessage() for r in caplog.records)


def test_pemuatan_bersamaan_hanya_membuat_satu_analyzer(monkeypatch):
    created = []

    class Fake:
        def __init__(self, ckpt, tok):
            created.append(self)
            time.sleep(0.2)

    monkeypatch.setattr(analyzer, "_analyzer", None)
    monkeypatch.setattr(analyzer, "model_ready", lambda: True)
    monkeypatch.setattr(analyzer, "ModelAnalyzer", Fake)
    results = []
    threads = [threading.Thread(target=lambda: results.append(analyzer.get_analyzer())) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert len(created) == 1
    assert len(results) == 5
    assert all(r is results[0] for r in results)
