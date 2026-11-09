"""Bilingual HTML receipt for a merchant order.

This is a payment receipt, not a ZATCA-compliant tax invoice (e-invoicing requires
a separate, certified integration; see docs).
"""

from html import escape

from app.core.money import halalas_to_sar
from app.modules.merchants.models import Merchant
from app.modules.orders.models import MerchantOrder, Order
from app.modules.payments.models import Payment
from app.modules.stores.models import Store


def _sar(value: int) -> str:
    return f"{halalas_to_sar(value):,.2f} SAR"


def render_receipt(order: Order, mo: MerchantOrder, store: Store, merchant: Merchant, payment: Payment | None) -> str:
    rows = "".join(
        f"<tr><td>{escape(i.title)}</td><td>{i.quantity}</td><td>{_sar(i.unit_price - i.unit_discount)}</td>"
        f"<td>{_sar(i.line_total)}</td></tr>"
        for i in mo.items
    )
    test_banner = (
        "<p class='test'>TEST PAYMENT — NO REAL MONEY · دفع تجريبي — لا توجد أموال حقيقية</p>"
        if payment and payment.is_test
        else ""
    )
    vat_line = f"<p>VAT No. / الرقم الضريبي: {escape(merchant.vat_number)}</p>" if merchant.vat_number else ""
    paid = payment.paid_at.isoformat() if payment and payment.paid_at else "—"
    if mo.delivery_method == "PICKUP":
        delivery_line = "<tr><td>Pickup / الاستلام من المتجر</td><td>0.00 SAR</td></tr>"
    elif mo.delivery_method == "DELIVERY":
        waived = f" (−{_sar(mo.delivery_fee_waived)} free delivery / توصيل مجاني)" if mo.delivery_fee_waived else ""
        delivery_line = f"<tr><td>Delivery / التوصيل{waived}</td><td>{_sar(mo.delivery_fee)}</td></tr>"
    else:
        delivery_line = ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Receipt {escape(mo.number)}</title>
<style>body{{font-family:system-ui,'Noto Naskh Arabic',sans-serif;max-width:720px;margin:2rem auto;color:#111}}
table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid #ddd;padding:.5rem;text-align:start}}
.test{{background:#fde68a;padding:.5rem;font-weight:600}}.totals td{{border:0}}</style></head>
<body>
{test_banner}
<h1>Receipt · إيصال</h1>
<p>Order / الطلب: {escape(mo.number)} · {order.created_at:%Y-%m-%d}</p>
<p>Seller / البائع: {escape(store.name)} ({escape(merchant.business_name)})</p>
{vat_line}
<p>Customer / العميل: {escape(order.contact_name)} · {escape(order.contact_phone)}</p>
<table><thead><tr><th>Item / المنتج</th><th>Qty / الكمية</th><th>Unit / السعر</th><th>Total / الإجمالي</th></tr></thead>
<tbody>{rows}</tbody></table>
<table class="totals">
<tr><td>Subtotal / المجموع الفرعي</td><td>{_sar(mo.items_subtotal)}</td></tr>
<tr><td>Discount / الخصم</td><td>-{_sar(mo.discount_total)}</td></tr>
{delivery_line}
<tr><td>VAT {mo.vat_rate}% / ضريبة القيمة المضافة</td><td>{_sar(mo.vat_total)}</td></tr>
<tr><td><strong>Total / الإجمالي</strong></td><td><strong>{_sar(mo.total)}</strong></td></tr>
<tr><td>Refunded / المسترد</td><td>{_sar(payment.refunded_amount if payment else 0)}</td></tr>
</table>
<p>Payment status / حالة الدفع: {escape(payment.status if payment else "—")} · Paid at / وقت الدفع: {paid}</p>
</body></html>"""
