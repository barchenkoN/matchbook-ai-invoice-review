"""Reproducible synthetic invoices; labels are not model outputs."""

import hashlib
import json
from decimal import Decimal

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select

from app import db, service, worker

SUPPLIERS = [
    "Nordline Supply",
    "Atlas Components",
    "Meridian Packaging",
    "Forma Industrial",
    "Cobalt Wholesale",
    "Pine & Paper",
]


def generate():
    folder = db.ROOT / "fixtures"
    folder.mkdir(exist_ok=True)
    catalog = []
    # Four development layouts (36 docs); two final unseen layouts (24 docs).
    for layout, supplier in enumerate(SUPPLIERS):
        count = 9 if layout < 4 else 12
        for index in range(count):
            number = f"{layout + 1}{index + 1:03d}"
            quantity = 100 if index % 3 == 0 else 80
            price = "13.00" if index % 4 == 0 else "12.50"
            amount = str(Decimal(quantity) * Decimal(price))
            payload = dict(
                supplier=supplier,
                invoice_number=f"INV-2026-{number}",
                invoice_date="2026-09-01",
                currency="EUR",
                po_number=f"PO-{number}",
                subtotal=amount,
                tax="0.00",
                total=amount,
                items=[
                    dict(
                        sku="BOX-042",
                        description="Archive storage box",
                        quantity=str(quantity),
                        unit_price=price,
                        line_total=amount,
                    )
                ],
            )
            order = dict(
                id=payload["po_number"],
                supplier=supplier,
                currency="EUR",
                receipt_id=f"GR-{number}",
                source="synthetic sandbox",
                items=[
                    dict(
                        sku="BOX-042",
                        description="Archive storage box",
                        ordered="100",
                        received="80",
                        unit_price="12.50",
                    )
                ],
            )
            path = folder / (payload["invoice_number"] + ".pdf")
            canvas = Canvas(str(path), pagesize=A4, invariant=1)
            width, height = A4
            left = 48 if layout % 2 == 0 else 66
            accent = ["#344BC5", "#285D59", "#6D486E", "#535B6A", "#315F7A", "#805939"][layout]
            canvas.setFillColor(HexColor(accent))
            canvas.rect(0, height - 14, width, 14, fill=1, stroke=0)
            canvas.setFont("Helvetica-Bold", 24)
            canvas.drawString(left, height - 78, supplier)
            canvas.setFillColor(HexColor("#626A80"))
            canvas.setFont("Helvetica", 10)
            canvas.drawString(left, height - 101, "Supplier document / synthetic portfolio sample")
            canvas.setFillColor(HexColor("#24283F"))
            canvas.setFont("Helvetica-Bold", 30)
            canvas.drawString(left, height - 166, "INVOICE")
            canvas.setFont("Helvetica", 11)
            details = [
                f"Invoice number: {payload['invoice_number']}",
                f"Invoice date: {payload['invoice_date']}",
                f"Purchase order: {payload['po_number']}",
                "Currency: EUR",
            ]
            if layout >= 4:
                details = details[::-1]
            for n, line in enumerate(details):
                canvas.drawString(left, height - 197 - n * 22, line)
            canvas.setFont("Helvetica", 10)
            canvas.drawString(left, height - 310, "Bill to: Alder Works / demonstration company")
            y = height - 360
            canvas.setFillColor(HexColor("#EDF0F7"))
            canvas.rect(left - 8, y - 10, width - left * 2 + 16, 29, fill=1, stroke=0)
            canvas.setFillColor(HexColor("#24283F"))
            canvas.setFont("Helvetica-Bold", 9)
            columns = [(left, "SKU / description"), (335, "Qty"), (393, "Unit price"), (492, "Amount")]
            for x, label in columns:
                canvas.drawString(x, y, label)
            canvas.setFont("Helvetica", 10)
            canvas.drawString(left, y - 37, "BOX-042  Archive storage box")
            canvas.drawRightString(353, y - 37, str(quantity))
            canvas.drawRightString(441, y - 37, price)
            canvas.drawRightString(539, y - 37, amount)
            canvas.setStrokeColor(HexColor("#E0E3ED"))
            canvas.line(left, y - 57, width - left, y - 57)
            for n, (label, value) in enumerate(
                [("Subtotal", amount), ("Tax", "0.00"), ("Total EUR", amount)]
            ):
                canvas.setFont("Helvetica-Bold" if n == 2 else "Helvetica", 14 if n == 2 else 11)
                canvas.drawString(350, y - 102 - n * 29, label)
                canvas.drawRightString(539, y - 102 - n * 29, value)
            canvas.setFont("Helvetica", 9)
            canvas.setFillColor(HexColor("#626A80"))
            canvas.drawString(left, 100, "No payment required. All names, orders and amounts are fictional.")
            canvas.drawString(left, 83, "Zero-tax example. Not a tax invoice for commercial use.")
            canvas.drawString(left, 48, "Matchbook test corpus")
            canvas.drawRightString(width - left, 48, "1 / 1")
            canvas.save()
            catalog.append(
                dict(
                    file=path.name,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    layout=layout,
                    split="development" if layout < 4 else "holdout",
                    expected=payload,
                    order=order,
                )
            )
    (folder / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Created {len(catalog)} synthetic invoices.")
    return catalog


def seed():
    catalog_path = db.ROOT / "fixtures" / "catalog.json"
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else generate()
    engine = db.make_engine()
    with engine.begin() as conn:
        for sample in catalog:
            if not conn.execute(
                select(db.orders.c.id).where(db.orders.c.id == sample["order"]["id"])
            ).scalar():
                conn.execute(db.orders.insert().values(**sample["order"]))
    # Two exception cases + four matched invoices, all explicitly replayed.
    selected = [catalog[0], catalog[1], catalog[9], catalog[10], catalog[19], catalog[28]]
    for sample in selected:
        path = db.ROOT / "fixtures" / sample["file"]
        service.intake(engine, path.read_bytes(), sample["file"], "replay", "demo setup")
    while job := db.claim(engine, "seed"):
        worker.run_job(engine, job)
    print("Six replay examples ready; no model inference claimed.")


if __name__ == "__main__":
    seed()
