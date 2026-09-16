import copy

from app.extraction import reconcile_explicit_source


def invoice():
    return dict(
        supplier="Test seller",
        invoice_number="TEST-1",
        invoice_date="2026-09-01",
        currency="EUR",
        po_number="PO-1",
        subtotal="0.00",
        tax="0.00",
        total="0.00",
        items=[dict(sku="A-1", description="Product", quantity="1", unit_price="2.50", line_total="25.00")],
    )


def row(text):
    return {"text": text, "page": 1, "box": [0, 0, 1, 1]}


def test_printed_values_correct_model_without_repairing_document_math():
    obj = invoice()
    original = copy.deepcopy(obj)
    result, changes = reconcile_explicit_source(
        obj, [row("Subtotal 25.00"), row("Total EUR 26.00"), row("A-1 Product 10 2.50 25.00")]
    )
    assert result["subtotal"] == "25.00" and result["total"] == "26.00"
    assert result["items"][0]["quantity"] == "10"
    assert obj == original
    assert len(changes) == 3


def test_ambiguous_or_absent_source_never_synthesizes_replacement():
    obj = invoice()
    result, changes = reconcile_explicit_source(obj, [row("Subtotal 25.00"), row("Subtotal 35.00")])
    assert result == obj and changes == []
