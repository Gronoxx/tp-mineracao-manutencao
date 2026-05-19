"""Testes do curador — `extracao/execucao/filtro_smells.py`.

Foco PR 4: a rota `/review` exige justificativa para `noisy`/`rejected`,
persiste `justificativa` e `confianca` no sidecar, valida `confianca`.
"""
import json

import pytest

from core.schema import ReviewBlock
from extracao.execucao.filtro_smells import create_app


@pytest.fixture
def curador(tmp_path):
    """Cliente de teste Flask + caminho do diretório de vereditos."""
    reviews_dir = tmp_path / "reviews"
    app = create_app(tmp_path / "raw", reviews_dir, limit=200)
    app.config["TESTING"] = True
    return app.test_client(), reviews_dir


def _sidecar_records(reviews_dir, smell="long_method"):
    path = reviews_dir / f"{smell}.reviews.jsonl"
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def test_rejected_sem_justificativa_falha(curador):
    client, _ = curador
    resp = client.post("/review", json={
        "smell": "long_method", "id": "p1", "status": "rejected"})
    data = resp.get_json()
    assert data["ok"] is False
    assert "justificativa" in data["error"].lower()


def test_noisy_sem_justificativa_falha(curador):
    client, _ = curador
    resp = client.post("/review", json={
        "smell": "long_method", "id": "p2", "status": "noisy",
        "before_clean": "def f(): pass", "after_clean": "def f(): return 1"})
    assert resp.get_json()["ok"] is False


def test_rejected_com_justificativa_grava_no_sidecar(curador):
    client, reviews_dir = curador
    resp = client.post("/review", json={
        "smell": "long_method", "id": "p3", "status": "rejected",
        "justificativa": "commit mistura feature nova, nao e refatoracao"})
    assert resp.get_json()["ok"] is True
    rec = _sidecar_records(reviews_dir)[0]
    assert rec["status"] == "rejected"
    assert rec["justificativa"] == "commit mistura feature nova, nao e refatoracao"


def test_clean_dispensa_justificativa(curador):
    client, _ = curador
    resp = client.post("/review", json={
        "smell": "long_method", "id": "p4", "status": "clean"})
    assert resp.get_json()["ok"] is True


def test_confianca_persiste(curador):
    client, reviews_dir = curador
    client.post("/review", json={
        "smell": "long_method", "id": "p5", "status": "clean", "confianca": "alta"})
    rec = _sidecar_records(reviews_dir)[0]
    assert rec["confianca"] == "alta"


def test_confianca_ausente_fica_none(curador):
    client, reviews_dir = curador
    client.post("/review", json={
        "smell": "long_method", "id": "p6", "status": "clean"})
    rec = _sidecar_records(reviews_dir)[0]
    assert rec["confianca"] is None


def test_confianca_invalida_falha(curador):
    client, _ = curador
    resp = client.post("/review", json={
        "smell": "long_method", "id": "p7", "status": "clean", "confianca": "altissima"})
    assert resp.get_json()["ok"] is False


def test_review_block_aceita_campos_novos():
    """O schema unificado tem de validar o registro produzido pelo curador."""
    rb = ReviewBlock(status="rejected", justificativa="ruido", confianca="baixa")
    assert rb.justificativa == "ruido" and rb.confianca == "baixa"
