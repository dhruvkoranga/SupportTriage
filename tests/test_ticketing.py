from support_triage.ticketing import add_internal_note, get_ticket


def test_get_ticket_returns_existing_ticket():
    result = get_ticket.invoke({"ticket_id": "T-1001"})
    assert "Order #4821 payment failing" in result
    assert "status=open" in result


def test_get_ticket_missing_ticket():
    result = get_ticket.invoke({"ticket_id": "T-9999"})
    assert "No ticket found" in result


def test_add_internal_note_persists_and_is_visible_via_get_ticket():
    add_internal_note.invoke({"ticket_id": "T-1002", "note": "test note from pytest"})
    result = get_ticket.invoke({"ticket_id": "T-1002"})
    assert "test note from pytest" in result


def test_add_internal_note_missing_ticket():
    result = add_internal_note.invoke({"ticket_id": "T-9999", "note": "irrelevant"})
    assert "No ticket found" in result
