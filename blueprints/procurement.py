from datetime import date
from decimal import Decimal, InvalidOperation
import uuid

import psycopg2
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from erp_common import active_branch, db_cursor, role_required


procurement_bp = Blueprint("procurement", __name__, url_prefix="/procurement")
BUYER_ROLES = ("admin", "procurement_officer")


def _branch(cur):
    branch = active_branch(cur, session["user_id"], session.get("branch_id"))
    if branch:
        session["branch_id"] = branch["branch_id"]
        session["branch_name"] = branch["branch_name"]
    return branch


def _audit_context(cur):
    cur.execute(
        "SELECT set_config('hms.user_id', %s, TRUE), set_config('hms.username', %s, TRUE)",
        (str(session["user_id"]), session.get("username", "")),
    )


def _page():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


def _amount(raw, label="amount"):
    try:
        value = Decimal(raw or "0")
    except (InvalidOperation, TypeError):
        raise ValueError(f"Enter a valid {label}.")
    if not value.is_finite() or value < 0 or value > Decimal("9999999999.99"):
        raise ValueError(f"{label.title()} must be between 0 and 9,999,999,999.99.")
    try:
        excess_precision = value != value.quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"{label.title()} must be a valid monetary amount.")
    if excess_precision:
        raise ValueError(f"{label.title()} can have up to two decimal places.")
    return value


def _paginate(cur, table, branch_id):
    page, per_page = _page(), 50
    cur.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE branch_id = %s", (branch_id,))
    total = cur.fetchone()["total"]
    total_pages = max(1, (total + per_page - 1) // per_page)
    return min(page, total_pages), per_page, total, total_pages


@procurement_bp.get("/")
@role_required(*BUYER_ROLES)
def dashboard():
    with db_cursor() as cur:
        branch = _branch(cur)
        metrics = {"vendors": 0, "open_requisitions": 0, "open_orders": 0, "unpaid_invoices": 0}
        if branch:
            cur.execute("SELECT COUNT(*) AS total FROM vendors WHERE branch_id = %s AND is_active = TRUE", (branch["branch_id"],))
            metrics["vendors"] = cur.fetchone()["total"]
            cur.execute(
                """SELECT COUNT(*) AS total FROM purchase_requisitions
                   WHERE branch_id = %s AND status IN ('submitted', 'approved')""",
                (branch["branch_id"],),
            )
            metrics["open_requisitions"] = cur.fetchone()["total"]
            cur.execute(
                """SELECT COUNT(*) AS total FROM purchase_orders
                   WHERE branch_id = %s AND status IN ('approved', 'sent', 'partially_received')""",
                (branch["branch_id"],),
            )
            metrics["open_orders"] = cur.fetchone()["total"]
            cur.execute(
                """SELECT COUNT(*) AS total FROM vendor_invoices
                   WHERE branch_id = %s AND status IN ('received', 'approved', 'partially_paid')""",
                (branch["branch_id"],),
            )
            metrics["unpaid_invoices"] = cur.fetchone()["total"]
    return render_template("procurement/dashboard.html", branch=branch, metrics=metrics)


@procurement_bp.route("/vendors", methods=["GET", "POST"])
@role_required(*BUYER_ROLES)
def vendors():
    if request.method == "POST":
        code = request.form.get("vendor_code", "").strip().upper()
        name = request.form.get("vendor_name", "").strip()
        contact = request.form.get("contact_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        try:
            terms = int(request.form.get("payment_terms_days", "30"))
        except ValueError:
            terms = -1
        if (
            not code or len(code) > 40 or not name or len(name) > 150 or
            len(contact) > 100 or len(email) > 150 or len(phone) > 30 or
            terms < 0 or terms > 3650
        ):
            flash("Check the vendor fields and payment terms.", "error")
            return redirect(url_for("procurement.vendors"))
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Create a branch and assign procurement access first.", "error")
                    return redirect(url_for("procurement.dashboard"))
                _audit_context(cur)
                cur.execute(
                    """INSERT INTO vendors
                           (branch_id, vendor_code, vendor_name, contact_name, email, phone, address, payment_terms_days)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (branch["branch_id"], code, name, contact or None, email or None, phone or None, address or None, terms),
                )
                cur.connection.commit()
            flash("Vendor added.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to create procurement vendor")
            flash("Vendor could not be saved. Check that the vendor code is unique.", "error")
        return redirect(url_for("procurement.vendors"))

    with db_cursor() as cur:
        branch = _branch(cur)
        vendors_page, page, total, total_pages = [], 1, 0, 1
        if branch:
            page, per_page, total, total_pages = _paginate(cur, "vendors", branch["branch_id"])
            cur.execute(
                """SELECT vendor_id, vendor_code, vendor_name, contact_name, email,
                          phone, payment_terms_days, is_active
                   FROM vendors WHERE branch_id = %s
                   ORDER BY vendor_name LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            vendors_page = cur.fetchall()
    return render_template(
        "procurement/vendors.html", branch=branch, vendors=vendors_page,
        page=page, total=total, total_pages=total_pages,
    )


@procurement_bp.route("/requisitions", methods=["GET", "POST"])
@role_required(*BUYER_ROLES)
def requisitions():
    if request.method == "POST":
        description = request.form.get("item_description", "").strip()
        justification = request.form.get("justification", "").strip()
        try:
            quantity = Decimal(request.form.get("quantity", ""))
            cost = _amount(request.form.get("estimated_unit_cost"), "estimated unit cost")
        except (InvalidOperation, ValueError):
            flash("Enter a valid quantity and estimated cost.", "error")
            return redirect(url_for("procurement.requisitions"))
        if (
            not description or len(description) > 255 or
            not quantity.is_finite() or quantity <= 0 or quantity > Decimal("999999999999.999") or
            len(justification) > 2000
        ):
            flash("Review the item description, quantity, and justification.", "error")
            return redirect(url_for("procurement.requisitions"))
        medicine_id = request.form.get("medicine_id") or None
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Create a branch and assign procurement access first.", "error")
                    return redirect(url_for("procurement.dashboard"))
                if medicine_id:
                    cur.execute("SELECT medicine_id FROM medicines WHERE medicine_id = %s", (medicine_id,))
                    if not cur.fetchone():
                        flash("Choose an existing medicine.", "error")
                        return redirect(url_for("procurement.requisitions"))
                _audit_context(cur)
                number = f"REQ-{date.today():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
                cur.execute(
                    """INSERT INTO purchase_requisitions
                           (branch_id, requisition_number, requested_by, justification)
                       VALUES (%s, %s, %s, %s)
                       RETURNING requisition_id""",
                    (branch["branch_id"], number, session["user_id"], justification or None),
                )
                requisition_id = cur.fetchone()["requisition_id"]
                cur.execute(
                    """INSERT INTO purchase_requisition_lines
                           (requisition_id, item_description, medicine_id, quantity, estimated_unit_cost)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (requisition_id, description, medicine_id, quantity, cost),
                )
                cur.connection.commit()
            flash(f"Requisition {number} created as a draft.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to create purchase requisition")
            flash("Requisition could not be saved.", "error")
        return redirect(url_for("procurement.requisitions"))

    with db_cursor() as cur:
        branch = _branch(cur)
        rows, medicines, page, total, total_pages = [], [], 1, 0, 1
        if branch:
            page, per_page, total, total_pages = _paginate(cur, "purchase_requisitions", branch["branch_id"])
            cur.execute(
                """SELECT r.requisition_id, r.requisition_number, r.request_date,
                          r.status, r.justification, u.full_name AS requester,
                          l.item_description, l.quantity, l.estimated_unit_cost
                   FROM purchase_requisitions r
                   JOIN users u ON u.user_id = r.requested_by
                   LEFT JOIN purchase_requisition_lines l ON l.requisition_id = r.requisition_id
                   WHERE r.branch_id = %s ORDER BY r.created_at DESC
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            rows = cur.fetchall()
            cur.execute("SELECT medicine_id, medicine_name FROM medicines ORDER BY medicine_name LIMIT 500")
            medicines = cur.fetchall()
    return render_template(
        "procurement/requisitions.html", branch=branch, requisitions=rows, medicines=medicines,
        page=page, total=total, total_pages=total_pages,
    )


@procurement_bp.post("/requisitions/<int:req_id>/<action>")
@role_required(*BUYER_ROLES)
def update_requisition(req_id, action):
    transitions = {"submit": ("draft", "submitted"), "approve": ("submitted", "approved"), "reject": ("submitted", "rejected")}
    if action not in transitions:
        flash("Invalid requisition action.", "error")
        return redirect(url_for("procurement.requisitions"))
    expected, status = transitions[action]
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            if not branch:
                return redirect(url_for("procurement.dashboard"))
            _audit_context(cur)
            cur.execute(
                """UPDATE purchase_requisitions
                   SET status = %s, approved_by = %s, approved_at = CURRENT_TIMESTAMP
                   WHERE requisition_id = %s AND branch_id = %s AND status = %s""",
                (status, session["user_id"], req_id, branch["branch_id"], expected),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Requisition not found or in the wrong status.", "error")
                return redirect(url_for("procurement.requisitions"))
            cur.connection.commit()
        flash(f"Requisition {status}.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to update purchase requisition")
        flash("Requisition status could not be changed.", "error")
    return redirect(url_for("procurement.requisitions"))


@procurement_bp.route("/orders", methods=["GET", "POST"])
@role_required(*BUYER_ROLES)
def orders():
    if request.method == "POST":
        try:
            vendor_id = int(request.form.get("vendor_id", ""))
            quantity = Decimal(request.form.get("quantity", ""))
            unit_price = _amount(request.form.get("unit_price"), "unit price")
        except (ValueError, InvalidOperation):
            flash("Choose a vendor and enter a valid quantity and unit price.", "error")
            return redirect(url_for("procurement.orders"))
        description = request.form.get("item_description", "").strip()
        if not description or len(description) > 255 or not quantity.is_finite() or quantity <= 0 or quantity > Decimal("999999999999.999"):
            flash("Review the purchase order item and quantity.", "error")
            return redirect(url_for("procurement.orders"))
        medicine_id = request.form.get("medicine_id") or None
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Create a branch and assign procurement access first.", "error")
                    return redirect(url_for("procurement.dashboard"))
                cur.execute(
                    "SELECT vendor_id FROM vendors WHERE vendor_id = %s AND branch_id = %s AND is_active = TRUE",
                    (vendor_id, branch["branch_id"]),
                )
                if not cur.fetchone():
                    flash("Choose an active vendor in this branch.", "error")
                    return redirect(url_for("procurement.orders"))
                if medicine_id:
                    cur.execute("SELECT medicine_id FROM medicines WHERE medicine_id = %s", (medicine_id,))
                    if not cur.fetchone():
                        flash("Choose an existing medicine.", "error")
                        return redirect(url_for("procurement.orders"))
                _audit_context(cur)
                po_number = f"PO-{date.today():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
                total = quantity * unit_price
                cur.execute(
                    """INSERT INTO purchase_orders
                           (branch_id, po_number, vendor_id, order_date, status,
                            subtotal_amount, total_amount, created_by)
                       VALUES (%s, %s, %s, CURRENT_DATE, 'draft', %s, %s, %s)
                       RETURNING purchase_order_id""",
                    (branch["branch_id"], po_number, vendor_id, total, total, session["user_id"]),
                )
                po_id = cur.fetchone()["purchase_order_id"]
                cur.execute(
                    """INSERT INTO po_lines
                           (purchase_order_id, line_number, item_description, medicine_id, quantity, unit_price)
                       VALUES (%s, 1, %s, %s, %s, %s)""",
                    (po_id, description, medicine_id, quantity, unit_price),
                )
                cur.connection.commit()
            flash(f"Purchase order {po_number} saved as a draft.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to create purchase order")
            flash("Purchase order could not be saved.", "error")
        return redirect(url_for("procurement.orders"))

    with db_cursor() as cur:
        branch = _branch(cur)
        rows, vendor_rows, medicines, page, total, total_pages = [], [], [], 1, 0, 1
        if branch:
            page, per_page, total, total_pages = _paginate(cur, "purchase_orders", branch["branch_id"])
            cur.execute(
                """SELECT p.purchase_order_id, p.po_number, p.order_date, p.status,
                          p.total_amount, v.vendor_name
                   FROM purchase_orders p JOIN vendors v ON v.vendor_id = p.vendor_id
                   WHERE p.branch_id = %s ORDER BY p.order_date DESC
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            rows = cur.fetchall()
            cur.execute("SELECT vendor_id, vendor_name FROM vendors WHERE branch_id = %s AND is_active = TRUE ORDER BY vendor_name", (branch["branch_id"],))
            vendor_rows = cur.fetchall()
            cur.execute("SELECT medicine_id, medicine_name FROM medicines ORDER BY medicine_name LIMIT 500")
            medicines = cur.fetchall()
    return render_template(
        "procurement/orders.html", branch=branch, orders=rows, vendors=vendor_rows,
        medicines=medicines, page=page, total=total, total_pages=total_pages,
    )


@procurement_bp.post("/orders/<int:order_id>/<action>")
@role_required(*BUYER_ROLES)
def update_order(order_id, action):
    transitions = {"approve": ("draft", "approved"), "send": ("approved", "sent")}
    if action not in transitions:
        flash("Invalid purchase order action.", "error")
        return redirect(url_for("procurement.orders"))
    old_status, new_status = transitions[action]
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            _audit_context(cur)
            cur.execute(
                """UPDATE purchase_orders SET status = %s
                   WHERE purchase_order_id = %s AND branch_id = %s AND status = %s""",
                (new_status, order_id, branch["branch_id"] if branch else None, old_status),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Purchase order not found or in the wrong status.", "error")
                return redirect(url_for("procurement.orders"))
            cur.connection.commit()
        flash(f"Purchase order {new_status}.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to update purchase order")
        flash("Purchase order status could not be changed.", "error")
    return redirect(url_for("procurement.orders"))


@procurement_bp.route("/receipts", methods=["GET", "POST"])
@role_required(*BUYER_ROLES)
def receipts():
    if request.method == "POST":
        try:
            po_line_id = int(request.form.get("po_line_id", ""))
            quantity = Decimal(request.form.get("quantity_received", ""))
        except (ValueError, InvalidOperation):
            flash("Select a purchase order line and enter received quantity.", "error")
            return redirect(url_for("procurement.receipts"))
        if not quantity.is_finite() or quantity <= 0:
            flash("Received quantity must be greater than zero.", "error")
            return redirect(url_for("procurement.receipts"))
        notes = request.form.get("notes", "").strip()
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Create a branch and assign procurement access first.", "error")
                    return redirect(url_for("procurement.dashboard"))
                cur.execute(
                    """SELECT l.po_line_id, l.purchase_order_id, l.item_description,
                              l.medicine_id, l.quantity, o.status
                       FROM po_lines l JOIN purchase_orders o USING (purchase_order_id)
                       WHERE l.po_line_id = %s AND o.branch_id = %s
                         AND o.status IN ('sent', 'partially_received') FOR UPDATE""",
                    (po_line_id, branch["branch_id"]),
                )
                po_line = cur.fetchone()
                if not po_line or quantity > Decimal(po_line["quantity"]):
                    flash("Line is not receivable or the quantity exceeds the order line.", "error")
                    return redirect(url_for("procurement.receipts"))
                if po_line["medicine_id"] and quantity != quantity.to_integral_value():
                    flash("Received medicine quantity must be a whole number.", "error")
                    return redirect(url_for("procurement.receipts"))
                cur.execute(
                    """SELECT COALESCE(SUM(gl.quantity_received), 0) AS received
                       FROM grn_lines gl JOIN grn g USING (grn_id)
                       WHERE gl.po_line_id = %s AND g.status = 'received'""",
                    (po_line_id,),
                )
                already_received = Decimal(cur.fetchone()["received"])
                if already_received + quantity > Decimal(po_line["quantity"]):
                    flash("Received quantity would exceed the remaining ordered amount.", "error")
                    return redirect(url_for("procurement.receipts"))
                _audit_context(cur)
                grn_number = f"GRN-{date.today():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
                cur.execute(
                    """INSERT INTO grn
                           (branch_id, grn_number, purchase_order_id, received_by, status, notes)
                       VALUES (%s, %s, %s, %s, 'received', %s)
                       RETURNING grn_id""",
                    (branch["branch_id"], grn_number, po_line["purchase_order_id"], session["user_id"], notes or None),
                )
                grn_id = cur.fetchone()["grn_id"]
                cur.execute(
                    """INSERT INTO grn_lines (grn_id, po_line_id, quantity_received, notes)
                       VALUES (%s, %s, %s, %s)""",
                    (grn_id, po_line_id, quantity, notes or None),
                )
                if po_line["medicine_id"]:
                    cur.execute(
                        """SELECT inventory_id FROM inventory
                           WHERE branch_id = %s AND medicine_id = %s
                           ORDER BY inventory_id LIMIT 1 FOR UPDATE""",
                        (branch["branch_id"], po_line["medicine_id"]),
                    )
                    inventory = cur.fetchone()
                    if inventory:
                        cur.execute(
                            """UPDATE inventory SET quantity = quantity + %s,
                                      last_updated = CURRENT_TIMESTAMP
                               WHERE inventory_id = %s""",
                            (int(quantity), inventory["inventory_id"]),
                        )
                    else:
                        cur.execute(
                            """INSERT INTO inventory (medicine_id, quantity, branch_id)
                               VALUES (%s, %s, %s)""",
                            (po_line["medicine_id"], int(quantity), branch["branch_id"]),
                        )
                cur.execute(
                    """SELECT COUNT(*) AS line_count,
                              COUNT(*) FILTER (
                                  WHERE COALESCE(received.total_received, 0) >= pol.quantity
                              ) AS complete_lines,
                              COUNT(*) FILTER (
                                  WHERE COALESCE(received.total_received, 0) > 0
                              ) AS started_lines
                       FROM po_lines pol
                       LEFT JOIN (
                           SELECT gl.po_line_id, SUM(gl.quantity_received) AS total_received
                           FROM grn_lines gl JOIN grn g USING (grn_id)
                           WHERE g.status = 'received'
                           GROUP BY gl.po_line_id
                       ) received ON received.po_line_id = pol.po_line_id
                       WHERE pol.purchase_order_id = %s""",
                    (po_line["purchase_order_id"],),
                )
                order_totals = cur.fetchone()
                if order_totals["complete_lines"] == order_totals["line_count"]:
                    next_status = "received"
                elif order_totals["started_lines"]:
                    next_status = "partially_received"
                else:
                    next_status = "sent"
                cur.execute(
                    "UPDATE purchase_orders SET status = %s WHERE purchase_order_id = %s",
                    (next_status, po_line["purchase_order_id"]),
                )
                cur.connection.commit()
            flash(f"Goods receipt {grn_number} recorded.", "success")
        except ValueError as error:
            flash(str(error), "error")
        except psycopg2.Error:
            current_app.logger.exception("Unable to record goods receipt")
            flash("Goods receipt and inventory could not be updated.", "error")
        return redirect(url_for("procurement.receipts"))

    with db_cursor() as cur:
        branch = _branch(cur)
        open_lines, receipt_rows = [], []
        if branch:
            cur.execute(
                """SELECT l.po_line_id, l.item_description, l.quantity, o.po_number,
                          v.vendor_name,
                          COALESCE(SUM(gl.quantity_received) FILTER (WHERE g.grn_id IS NOT NULL), 0) AS received
                   FROM po_lines l
                   JOIN purchase_orders o USING (purchase_order_id)
                   JOIN vendors v ON v.vendor_id = o.vendor_id
                   LEFT JOIN grn_lines gl ON gl.po_line_id = l.po_line_id
                   LEFT JOIN grn g ON g.grn_id = gl.grn_id AND g.status = 'received'
                   WHERE o.branch_id = %s AND o.status IN ('sent', 'partially_received')
                   GROUP BY l.po_line_id, o.po_number, v.vendor_name
                   ORDER BY o.po_number LIMIT 500""",
                (branch["branch_id"],),
            )
            open_lines = [row for row in cur.fetchall() if Decimal(row["received"]) < Decimal(row["quantity"])]
            cur.execute(
                """SELECT g.grn_number, g.received_date, g.status, o.po_number,
                          v.vendor_name
                   FROM grn g JOIN purchase_orders o USING (purchase_order_id)
                   JOIN vendors v ON v.vendor_id = o.vendor_id
                   WHERE g.branch_id = %s ORDER BY g.received_date DESC LIMIT 50""",
                (branch["branch_id"],),
            )
            receipt_rows = cur.fetchall()
    return render_template("procurement/receipts.html", branch=branch, open_lines=open_lines, receipts=receipt_rows)


@procurement_bp.route("/invoices", methods=["GET", "POST"])
@role_required("admin", "procurement_officer", "accountant")
def invoices():
    if request.method == "POST":
        try:
            vendor_id = int(request.form.get("vendor_id", ""))
            invoice_date = date.fromisoformat(request.form.get("invoice_date", ""))
            due_date = date.fromisoformat(request.form["due_date"]) if request.form.get("due_date") else None
            subtotal = _amount(request.form.get("subtotal_amount"), "subtotal")
            tax = _amount(request.form.get("tax_amount"), "tax")
        except (ValueError, InvalidOperation) as error:
            flash(str(error) or "Enter valid vendor invoice details.", "error")
            return redirect(url_for("procurement.invoices"))
        invoice_number = request.form.get("invoice_number", "").strip()
        if not invoice_number or len(invoice_number) > 80 or (due_date and due_date < invoice_date):
            flash("Check the invoice number and due date.", "error")
            return redirect(url_for("procurement.invoices"))
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Create a branch and assign procurement access first.", "error")
                    return redirect(url_for("procurement.dashboard"))
                cur.execute("SELECT vendor_id FROM vendors WHERE vendor_id = %s AND branch_id = %s", (vendor_id, branch["branch_id"]))
                if not cur.fetchone():
                    flash("Choose a vendor in the active branch.", "error")
                    return redirect(url_for("procurement.invoices"))
                _audit_context(cur)
                cur.execute(
                    """INSERT INTO vendor_invoices
                           (branch_id, vendor_id, invoice_number, invoice_date, due_date,
                            subtotal_amount, tax_amount, total_amount, created_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        branch["branch_id"], vendor_id, invoice_number, invoice_date, due_date,
                        subtotal, tax, subtotal + tax, session["user_id"],
                    ),
                )
                cur.connection.commit()
            flash("Vendor invoice recorded.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to record vendor invoice")
            flash("Vendor invoice could not be saved. Check that the invoice number is unique for this vendor.", "error")
        return redirect(url_for("procurement.invoices"))

    with db_cursor() as cur:
        branch = _branch(cur)
        invoices_page, vendors_page, page, total, total_pages = [], [], 1, 0, 1
        if branch:
            page, per_page, total, total_pages = _paginate(cur, "vendor_invoices", branch["branch_id"])
            cur.execute(
                """SELECT i.vendor_invoice_id, i.invoice_number, i.invoice_date, i.due_date,
                          i.total_amount, i.status, v.vendor_name
                   FROM vendor_invoices i JOIN vendors v ON v.vendor_id = i.vendor_id
                   WHERE i.branch_id = %s ORDER BY i.invoice_date DESC
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            invoices_page = cur.fetchall()
            cur.execute("SELECT vendor_id, vendor_name FROM vendors WHERE branch_id = %s AND is_active = TRUE ORDER BY vendor_name", (branch["branch_id"],))
            vendors_page = cur.fetchall()
    return render_template(
        "procurement/invoices.html", branch=branch, invoices=invoices_page, vendors=vendors_page,
        page=page, total=total, total_pages=total_pages,
    )


@procurement_bp.post("/invoices/<int:invoice_id>/pay")
@role_required("admin", "accountant", "procurement_officer")
def pay_invoice(invoice_id):
    try:
        amount = _amount(request.form.get("amount"), "payment amount")
        payment_date = date.fromisoformat(request.form.get("payment_date", ""))
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("procurement.invoices"))
    method = request.form.get("payment_method", "")
    if amount <= 0 or method not in {"cash", "bank_transfer", "card", "cheque", "other"}:
        flash("Choose a positive amount and valid payment method.", "error")
        return redirect(url_for("procurement.invoices"))
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            if not branch:
                flash("No active branch is selected.", "error")
                return redirect(url_for("procurement.invoices"))
            cur.execute(
                """SELECT vendor_invoice_id, total_amount, status
                   FROM vendor_invoices
                   WHERE vendor_invoice_id = %s AND branch_id = %s
                   FOR UPDATE""",
                (invoice_id, branch["branch_id"]),
            )
            invoice = cur.fetchone()
            if not invoice or invoice["status"] in {"void", "paid"}:
                flash("Unpaid vendor invoice not found in the active branch.", "error")
                return redirect(url_for("procurement.invoices"))
            cur.execute(
                """SELECT COALESCE(SUM(amount), 0) AS paid
                   FROM payments
                   WHERE vendor_invoice_id = %s AND branch_id = %s AND status = 'posted'""",
                (invoice_id, branch["branch_id"]),
            )
            paid = Decimal(cur.fetchone()["paid"])
            remaining = Decimal(invoice["total_amount"]) - paid
            if amount > remaining:
                flash("Payment cannot exceed the remaining invoice balance.", "error")
                return redirect(url_for("procurement.invoices"))
            _audit_context(cur)
            number = f"PAY-{date.today():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
            cur.execute(
                """INSERT INTO payments
                       (branch_id, payment_number, direction, vendor_invoice_id,
                        amount, payment_date, payment_method, status, recorded_by)
                   VALUES (%s, %s, 'outgoing', %s, %s, %s, %s, 'posted', %s)""",
                (branch["branch_id"], number, invoice_id, amount, payment_date, method, session["user_id"]),
            )
            new_status = "paid" if amount == remaining else "partially_paid"
            cur.execute(
                "UPDATE vendor_invoices SET status = %s WHERE vendor_invoice_id = %s",
                (new_status, invoice_id),
            )
            cur.connection.commit()
        flash("Vendor payment recorded.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to record vendor payment")
        flash("Payment could not be recorded.", "error")
    return redirect(url_for("procurement.invoices"))
