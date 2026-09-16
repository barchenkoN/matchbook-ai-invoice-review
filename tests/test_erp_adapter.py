import json

import httpx
import pytest

from app import erp


def payload():
    return dict(
        supplier="Supplier",
        invoice_number="I-7",
        invoice_date="2026-09-01",
        currency="EUR",
        po_number="PO-7",
        total="25.00",
        items=[dict(sku="A-1", quantity="10", unit_price="2.50")],
    )


def test_erpnext_http_contract_draft_only_and_readback(monkeypatch):
    monkeypatch.setenv("ERP_MODE", "erpnext")
    monkeypatch.setenv("ERP_COMPANY", "Test company")
    requests = []

    def handle(request):
        requests.append(request)
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["docstatus"] == 0 and body["custom_matchbook_reference"] == "mb-test"
            return httpx.Response(200, json={"data": {"name": "PINV-TEST"}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "docstatus": 0,
                    "company": "Test company",
                    "supplier": "Supplier",
                    "bill_no": "I-7",
                    "currency": "EUR",
                    "grand_total": 25,
                    "custom_matchbook_reference": "mb-test",
                    "items": [{"item_code": "A-1", "qty": 10, "rate": 2.5}],
                }
            },
        )

    monkeypatch.setattr(
        erp,
        "client",
        lambda: httpx.Client(base_url="https://erp.example", transport=httpx.MockTransport(handle)),
    )
    assert erp.create_draft(None, "mb-test", payload()) == "PINV-TEST"
    assert [r.method for r in requests] == ["POST", "GET"]


def test_readback_rejects_wrong_supplier_even_if_total_matches(monkeypatch):
    monkeypatch.setenv("ERP_COMPANY", "Test company")
    with pytest.raises(ValueError, match="read-back"):
        erp.verify_remote(
            {
                "docstatus": 0,
                "company": "Test company",
                "supplier": "Wrong supplier",
                "bill_no": "I-7",
                "currency": "EUR",
                "grand_total": 25,
                "custom_matchbook_reference": "mb-test",
                "items": [{"item_code": "A-1", "qty": 10, "rate": 2.5}],
            },
            payload(),
            "mb-test",
        )
