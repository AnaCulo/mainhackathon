import pytest

from app.config import Settings


def load(monkeypatch, tmp_path, url):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("N8N_WEBHOOK_URL", url)
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "secret")
    return Settings.load()


@pytest.mark.parametrize(
    "url",
    [
        "https://n8n.example.test/webhook/protected-case",
        "http://127.0.0.1:5689/webhook/protected-case",
        "http://[::1]:5689/webhook/protected-case",
    ],
)
def test_accepts_https_or_numeric_loopback_http(monkeypatch, tmp_path, url):
    assert load(monkeypatch, tmp_path, url).webhook == url


@pytest.mark.parametrize(
    "url",
    [
        "http://n8n.example.test/webhook/protected-case",
        "http://localhost:5689/webhook/protected-case",
        "http://10.0.0.5:5689/webhook/protected-case",
        "http://user:pw@127.0.0.1:5689/webhook/protected-case",
    ],
)
def test_rejects_plain_http_off_loopback(monkeypatch, tmp_path, url):
    with pytest.raises(ValueError):
        load(monkeypatch, tmp_path, url)
