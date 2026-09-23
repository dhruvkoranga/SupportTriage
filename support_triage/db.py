"""Mock application database for the Diagnosis agent's DB query tool.

A real sqlite database (not just a dict) — parameterized queries here are the
same defense against SQL injection a production tool would need, even though
this data is in-memory (":memory:") and disposable: it resets on every
process start, same tradeoff as ticketing.py's in-memory store.
"""

import sqlite3

from langchain_core.tools import tool

_connection = sqlite3.connect(":memory:", check_same_thread=False)
_connection.execute(
    """
    CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        customer_email TEXT NOT NULL,
        status TEXT NOT NULL,
        last_updated TEXT NOT NULL
    )
    """
)
_connection.executemany(
    "INSERT INTO orders VALUES (?, ?, ?, ?)",
    [
        ("4821", "alex@example.com", "PROCESSING", "2026-09-20 10:12:09"),
        ("55", "jordan@example.com", "PENDING", "2026-09-21 09:00:00"),
        ("1190", "sam@example.com", "DELIVERED", "2026-09-18 16:45:00"),
    ],
)
_connection.commit()


@tool
def query_order_status(order_id: int | str) -> str:
    """Look up an order's current status, customer, and last-updated time by order ID."""
    order_id = str(order_id)
    row = _connection.execute(
        "SELECT order_id, customer_email, status, last_updated FROM orders WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    if row is None:
        return f"No order found with ID {order_id!r}."
    order_id_val, email, status, last_updated = row
    return f"Order {order_id_val}: status={status}, customer={email}, last_updated={last_updated}"
