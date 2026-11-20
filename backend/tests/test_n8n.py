from .doubles import BACKEND, CONTROL


def test_outage_then_retry(setup, submit):
    client, double, db = setup
    double.fault = "webhook"
    case = submit(CONTROL).json()
    with db.connection() as con:
        assert con.execute("SELECT state FROM outbox").fetchone()[0] == "pending"
    double.fault = None
    assert client.post("/deliveries/retry", headers=BACKEND).json() == {
        "deliveries": {case["case_id"]: "delivered"}
    }
    assert double.deliveries == [case, case]
    assert client.post("/deliveries/retry", headers=BACKEND).json() == {
        "deliveries": {}
    }
