"""Model-independent invoice rules. Amounts never use binary floating point."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field


class Line(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(min_length=1, max_length=80)
    description: str = Field(max_length=300)
    quantity: Decimal = Field(gt=0, le=100000, max_digits=12, decimal_places=3)
    unit_price: Decimal = Field(ge=0, le=1000000, max_digits=12, decimal_places=2)
    line_total: Decimal = Field(ge=0, le=1000000000, max_digits=14, decimal_places=2)


class Invoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier: str = Field(min_length=1, max_length=200)
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: date
    currency: str = Field(pattern="^[A-Z]{3}$")
    po_number: str = Field(min_length=1, max_length=100)
    subtotal: Decimal = Field(ge=0, le=1000000000, max_digits=14, decimal_places=2)
    tax: Decimal = Field(ge=0, le=1000000000, max_digits=14, decimal_places=2)
    total: Decimal = Field(ge=0, le=1000000000, max_digits=14, decimal_places=2)
    items: list[Line] = Field(min_length=1, max_length=20)


def money(value):
    return Decimal(str(value)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def validate_invoice(payload, order, evidence=None):
    issues = []

    def issue(code, title, detail, field="", line=None):
        issues.append(
            dict(code=code, title=title, detail=detail, field=field, line=line, severity="blocking")
        )

    try:
        invoice = Invoice.model_validate(payload)
    except Exception:
        issue(
            "schema",
            "Incomplete invoice data",
            "Complete the required fields and valid numeric values before review.",
        )
        return issues
    if invoice.currency != "EUR":
        issue("currency", "Unsupported currency", "This demo supports EUR invoices only.", "currency")
    if invoice.tax != 0:
        issue(
            "tax",
            "Tax requires an extended policy",
            "Version 1 supports zero-tax demonstration invoices only.",
            "tax",
        )
    if money(sum(x.line_total for x in invoice.items)) != money(invoice.subtotal):
        issue(
            "subtotal",
            "Line totals do not reconcile",
            "Sum of line amounts differs from the invoice subtotal.",
            "subtotal",
        )
    if money(invoice.subtotal + invoice.tax) != money(invoice.total):
        issue("total", "Invoice total does not reconcile", "Subtotal plus tax must equal the total.", "total")
    if not order:
        issue(
            "missing_order",
            "Purchase order not found",
            "Import or select a known purchase order before approval.",
            "po_number",
        )
        return issues
    if invoice.supplier.casefold().strip() != order["supplier"].casefold().strip():
        issue(
            "supplier",
            "Supplier does not match",
            "Invoice supplier differs from the purchase order.",
            "supplier",
        )
    if invoice.currency != order["currency"]:
        issue(
            "order_currency",
            "Order currency differs",
            "Invoice and purchase order must use the same currency.",
            "currency",
        )
    if not order.get("receipt_id"):
        issue("missing_receipt", "Goods receipt missing", "A confirmed receipt is required before approval.")
    known = {item["sku"]: item for item in order["items"]}
    seen = set()
    for index, item in enumerate(invoice.items):
        if item.sku in seen:
            issue(
                "duplicate_line", "Repeated SKU", "Repeated SKUs need manual consolidation.", "items", index
            )
        seen.add(item.sku)
        if money(item.quantity * item.unit_price) != money(item.line_total):
            issue(
                "line_total",
                "Line amount differs",
                "Quantity multiplied by unit price does not equal line amount.",
                "items",
                index,
            )
        match = known.get(item.sku)
        if not match:
            issue(
                "unknown_sku",
                "Item not on purchase order",
                f"{item.sku} has no exact supplier SKU mapping.",
                "items",
                index,
            )
            continue
        if item.quantity > Decimal(str(match["received"])):
            gap = item.quantity - Decimal(str(match["received"]))
            issue(
                "quantity",
                "Quantity exceeds goods received",
                f"{gap:g} extra units invoiced; received {match['received']}.",
                "items",
                index,
            )
        if money(item.unit_price) != money(match["unit_price"]):
            gap = money(item.unit_price) - money(match["unit_price"])
            issue(
                "price",
                "Unit price differs from order",
                f"EUR {gap:+.2f} per unit against agreed EUR {money(match['unit_price']):.2f}.",
                "items",
                index,
            )
    if evidence is not None:
        keys = [
            "supplier",
            "invoice_number",
            "invoice_date",
            "currency",
            "po_number",
            "subtotal",
            "tax",
            "total",
        ]
        keys += [
            f"items.{i}.{field}"
            for i in range(len(invoice.items))
            for field in ("sku", "quantity", "unit_price", "line_total")
        ]
        missing = [key for key in keys if not evidence.get(key)]
        if missing:
            issue(
                "source",
                "Fields need source verification",
                f"{len(missing)} critical values could not be located in the document. Review and save verified values.",
            )
    return issues
