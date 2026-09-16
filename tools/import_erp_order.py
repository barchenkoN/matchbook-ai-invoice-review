"""Read a real ERPNext order and receipt into the local reference store.

Requires configured ERP_URL/API credentials; never creates ERP records.
Unverified against a live ERPNext instance in this delivery.
"""

import argparse
from decimal import Decimal
from urllib.parse import quote

from sqlalchemy import select, update

from app import db, erp

parser = argparse.ArgumentParser()
parser.add_argument("purchase_order")
parser.add_argument("purchase_receipt")
args = parser.parse_args()
with erp.client() as client:
    po = client.get("/api/resource/Purchase Order/" + quote(args.purchase_order, safe=""))
    po.raise_for_status()
    receipt = client.get("/api/resource/Purchase Receipt/" + quote(args.purchase_receipt, safe=""))
    receipt.raise_for_status()
    order, received = po.json()["data"], receipt.json()["data"]
if order.get("docstatus") != 1 or received.get("docstatus") != 1 or order["supplier"] != received["supplier"]:
    raise ValueError("Use submitted order and receipt records for the same supplier.")
items = []
for row in order["items"]:
    matching = [
        x
        for x in received["items"]
        if x.get("purchase_order") == order["name"] and x.get("purchase_order_item") == row["name"]
    ]
    if len(matching) != 1:
        raise ValueError("Version 1 requires one unambiguous receipt row per purchase order row.")
    item = matching[0]
    if row.get("uom") != item.get("uom") or Decimal(str(item.get("billed_amt", 0))) != 0:
        raise ValueError("Unit conversions and already-billed receipts are unsupported.")
    items.append(
        {
            "sku": row["item_code"],
            "description": row.get("description", ""),
            "ordered": str(row["qty"]),
            "received": str(item["qty"]),
            "unit_price": str(row["rate"]),
        }
    )
payload = {
    "id": order["name"],
    "supplier": order["supplier"],
    "currency": order["currency"],
    "receipt_id": received["name"],
    "source": "ERPNext REST snapshot",
    "items": items,
}
engine = db.make_engine()
with engine.begin() as conn:
    if conn.execute(select(db.orders.c.id).where(db.orders.c.id == order["name"])).scalar():
        conn.execute(update(db.orders).where(db.orders.c.id == order["name"]).values(**payload))
    else:
        conn.execute(db.orders.insert().values(**payload))
print("Imported read-only ERP reference snapshot. Review source freshness before approval.")
