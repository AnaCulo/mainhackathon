import pytest

from .doubles import BACKEND, CONTROL, VOICE


@pytest.mark.parametrize("headers", [{}, VOICE, {"Authorization": "Bearer wrong"}])
def test_auth(setup, headers):
    client, double, _ = setup
    assert (
        client.post("/reports", json={"text": CONTROL}, headers=headers).status_code
        == 401
    )
    assert not double.requests


@pytest.mark.parametrize(
    "body",
    [
        '{"text":"sensitive@example.invalid"',
        '{"text":"  "}',
        '{"text":"report","status":"closed"}',
    ],
)
def test_bad_input(setup, body):
    client, double, _ = setup
    r = client.post(
        "/reports",
        content=body,
        headers={**BACKEND, "Content-Type": "application/json"},
    )
    assert (
        r.status_code == 422
        and "sensitive@example.invalid" not in r.text
        and not double.requests
    )


def test_model_malformed(setup, submit):
    setup[1].answer = "sensitive@example.invalid"
    r = submit(CONTROL)
    assert r.status_code == 502 and "sensitive@" not in r.text
    assert not setup[1].deliveries


def test_bounded_request(setup):
    client, double, _ = setup
    r = client.post("/reports", json={"text": "X" * 200000}, headers=BACKEND)
    assert r.status_code == 413 and not double.requests
