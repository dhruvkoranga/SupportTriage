from support_triage.db import query_order_status


def test_query_order_status_finds_existing_order():
    result = query_order_status.invoke({"order_id": "4821"})
    assert "PROCESSING" in result
    assert "alex@example.com" in result


def test_query_order_status_handles_int_order_id():
    # Regression test: a tool-calling model sometimes passes a numeric-looking
    # ID as an int rather than a string; Pydantic v2 won't coerce that for a
    # plain `str` field, so the tool itself has to accept and normalize it.
    result = query_order_status.invoke({"order_id": 55})
    assert "PENDING" in result


def test_query_order_status_missing_order():
    result = query_order_status.invoke({"order_id": "does-not-exist"})
    assert "No order found" in result
