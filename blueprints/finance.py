from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import uuid

import psycopg2
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from erp_common import active_branch, db_cursor, role_required


finance_bp = Blueprint("finance", __name__, url_prefix="/finance")
ACCOUNT_TYPES = {"asset", "liability", "equity", "revenue", "expense"}
BALANCES = {"debit", "credit"}
MAX_AMOUNT = Decimal("9999999999.99")
CENT = Decimal("0.01")


def _page_number():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


def _branch(cur):
    branch = active_branch(cur, session["user_id"], session.get("branch_id"))
    if branch:
        session["branch_id"] = branch["branch_id"]
        session["branch_name"] = branch["branch_name"]
    return branch


def _parse_amount(raw_value):
    try:
        amount = Decimal(raw_value)
    except (InvalidOperation, TypeError):
        raise ValueError("Enter valid debit and credit amounts.")
    if not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT:
        raise ValueError("Amounts must be between 0 and 9,999,999,999.99.")
    try:
        has_excess_precision = amount != amount.quantize(CENT)
    except InvalidOperation:
        raise ValueError("Enter a valid monetary amount.")
    if has_excess_precision:
        raise ValueError("Amounts can have no more than two decimal places.")
    return amount


def _entry_lines(form):
    account_ids = form.getlist("account_id")
    descriptions = form.getlist("line_description")
    debits = form.getlist("debit")
    credits = form.getlist("credit")
    if not (len(account_ids) == len(descriptions) == len(debits) == len(credits)):
        raise ValueError("Journal lines are incomplete. Review the form and try again.")
    if not 2 <= len(account_ids) <= 20:
        raise ValueError("A journal entry needs 2 to 20 lines.")

    lines = []
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")
    for account_id, description, debit_raw, credit_raw in zip(
        account_ids, descriptions, debits, credits
    ):
        try:
            parsed_account_id = int(account_id)
        except ValueError:
            raise ValueError("Select an account for every journal line.")
        if parsed_account_id < 1:
            raise ValueError("Select a valid account for every journal line.")

        description = description.strip()
        if len(description) > 255:
            raise ValueError("Line descriptions must be 255 characters or fewer.")
        debit = _parse_amount(debit_raw or "0")
        credit = _parse_amount(credit_raw or "0")
        if (debit > 0) == (credit > 0):
            raise ValueError("Each line must contain either a debit or a credit amount.")
        debit_total += debit
        credit_total += credit
        lines.append((parsed_account_id, description or None, debit, credit))

    if debit_total <= 0 or debit_total != credit_total:
        raise ValueError("Journal debits and credits must be equal and greater than zero.")
    return lines


@finance_bp.get("/")
@role_required("admin", "accountant")
def dashboard():
    with db_cursor() as cur:
        branch = _branch(cur)
        if branch:
            cur.execute(
                """SELECT
                       COUNT(*) FILTER (WHERE account_type = 'asset') AS asset_accounts,
                       COUNT(*) FILTER (WHERE account_type = 'liability') AS liability_accounts,
                       COUNT(*) FILTER (WHERE account_type = 'revenue') AS revenue_accounts,
                       COUNT(*) FILTER (WHERE account_type = 'expense') AS expense_accounts
                   FROM chart_of_accounts
                   WHERE branch_id = %s OR branch_id IS NULL""",
                (branch["branch_id"],),
            )
            account_counts = cur.fetchone()
            cur.execute(
                """SELECT COUNT(*) AS draft_count
                   FROM journal_entries
                   WHERE branch_id = %s AND status = 'draft'""",
                (branch["branch_id"],),
            )
            draft_count = cur.fetchone()["draft_count"]
        else:
            account_counts = {
                "asset_accounts": 0,
                "liability_accounts": 0,
                "revenue_accounts": 0,
                "expense_accounts": 0,
            }
            draft_count = 0
    return render_template(
        "finance/dashboard.html",
        branch=branch,
        account_counts=account_counts,
        draft_count=draft_count,
    )


@finance_bp.route("/accounts", methods=["GET", "POST"])
@role_required("admin", "accountant")
def accounts():
    if request.method == "POST":
        account_code = request.form.get("account_code", "").strip()
        account_name = request.form.get("account_name", "").strip()
        account_type = request.form.get("account_type", "").strip().lower()
        normal_balance = request.form.get("normal_balance", "").strip().lower()
        description = request.form.get("description", "").strip()
        try:
            parent_id = int(request.form.get("parent_account_id") or 0) or None
        except ValueError:
            flash("Choose a valid parent account.", "error")
            return redirect(url_for("finance.accounts"))

        if (
            not account_code or len(account_code) > 30 or
            not account_name or len(account_name) > 150 or
            account_type not in ACCOUNT_TYPES or normal_balance not in BALANCES or
            len(description) > 1000
        ):
            flash("Enter a valid account code, name, type, and normal balance.", "error")
            return redirect(url_for("finance.accounts"))

        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Ask an administrator to assign you to an active branch first.", "error")
                    return redirect(url_for("finance.dashboard"))
                if parent_id:
                    cur.execute(
                        """SELECT account_id FROM chart_of_accounts
                           WHERE account_id = %s AND is_active = TRUE
                             AND (branch_id = %s OR branch_id IS NULL)""",
                        (parent_id, branch["branch_id"]),
                    )
                    if not cur.fetchone():
                        flash("The parent account is not available in this branch.", "error")
                        return redirect(url_for("finance.accounts"))
                cur.execute(
                    """SELECT set_config('hms.user_id', %s, TRUE),
                              set_config('hms.username', %s, TRUE)""",
                    (str(session["user_id"]), session.get("username", "")),
                )
                cur.execute(
                    """INSERT INTO chart_of_accounts
                           (branch_id, account_code, account_name, account_type,
                            normal_balance, parent_account_id, description)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        branch["branch_id"], account_code, account_name,
                        account_type, normal_balance, parent_id, description or None,
                    ),
                )
                cur.connection.commit()
            flash("Account added to the chart of accounts.", "success")
            return redirect(url_for("finance.accounts"))
        except psycopg2.Error:
            current_app.logger.exception("Unable to create finance account")
            flash("The account could not be saved. Check that its code is unique and try again.", "error")
            return redirect(url_for("finance.accounts"))

    page = _page_number()
    per_page = 50
    with db_cursor() as cur:
        branch = _branch(cur)
        if not branch:
            accounts_page, total, total_pages, parents = [], 0, 1, []
            page = 1
        else:
            cur.execute(
                """SELECT COUNT(*) AS total FROM chart_of_accounts
                   WHERE branch_id = %s OR branch_id IS NULL""",
                (branch["branch_id"],),
            )
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT a.account_id, a.account_code, a.account_name,
                          a.account_type, a.normal_balance, a.is_active,
                          p.account_name AS parent_name
                   FROM chart_of_accounts a
                   LEFT JOIN chart_of_accounts p ON p.account_id = a.parent_account_id
                   WHERE a.branch_id = %s OR a.branch_id IS NULL
                   ORDER BY a.account_code
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            accounts_page = cur.fetchall()
            cur.execute(
                """SELECT account_id, account_code, account_name
                   FROM chart_of_accounts
                   WHERE is_active = TRUE AND (branch_id = %s OR branch_id IS NULL)
                   ORDER BY account_code LIMIT 500""",
                (branch["branch_id"],),
            )
            parents = cur.fetchall()
    return render_template(
        "finance/accounts.html",
        branch=branch,
        accounts=accounts_page,
        parents=parents,
        page=page,
        total=total,
        total_pages=total_pages,
    )


@finance_bp.route("/journals", methods=["GET", "POST"])
@role_required("admin", "accountant")
def journals():
    if request.method == "POST":
        description = request.form.get("description", "").strip()
        try:
            entry_date = date.fromisoformat(request.form.get("entry_date", ""))
            lines = _entry_lines(request.form)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("finance.journals"))
        if not description or len(description) > 500:
            flash("Enter a description up to 500 characters.", "error")
            return redirect(url_for("finance.journals"))

        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Ask an administrator to assign you to an active branch first.", "error")
                    return redirect(url_for("finance.dashboard"))
                account_ids = list({line[0] for line in lines})
                cur.execute(
                    """SELECT account_id FROM chart_of_accounts
                       WHERE account_id = ANY(%s) AND is_active = TRUE
                         AND (branch_id = %s OR branch_id IS NULL)""",
                    (account_ids, branch["branch_id"]),
                )
                accessible_ids = {row["account_id"] for row in cur.fetchall()}
                if accessible_ids != set(account_ids):
                    flash("One or more accounts are inactive or not available in this branch.", "error")
                    return redirect(url_for("finance.journals"))

                cur.execute(
                    """SELECT set_config('hms.user_id', %s, TRUE),
                              set_config('hms.username', %s, TRUE)""",
                    (str(session["user_id"]), session.get("username", "")),
                )
                entry_number = f"JE-{date.today():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
                cur.execute(
                    """INSERT INTO journal_entries
                           (branch_id, entry_number, entry_date, description, created_by)
                       VALUES (%s, %s, %s, %s, %s)
                       RETURNING journal_entry_id""",
                    (branch["branch_id"], entry_number, entry_date, description, session["user_id"]),
                )
                entry_id = cur.fetchone()["journal_entry_id"]
                for account_id, line_description, debit, credit in lines:
                    cur.execute(
                        """INSERT INTO journal_lines
                               (journal_entry_id, account_id, line_description, debit, credit)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (entry_id, account_id, line_description, debit, credit),
                    )
                cur.connection.commit()
            flash(f"Journal entry {entry_number} saved as a draft.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to create finance journal entry")
            flash("The journal entry could not be saved. No changes were committed.", "error")
        return redirect(url_for("finance.journals"))

    page = _page_number()
    per_page = 50
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    try:
        date_from = date.fromisoformat(start_date) if start_date else None
        date_to = date.fromisoformat(end_date) if end_date else None
    except ValueError:
        flash("Enter a valid date range.", "error")
        date_from = date_to = None
    if date_from and date_to and date_to < date_from:
        flash("The end date must be on or after the start date.", "error")
        date_from = date_to = None

    with db_cursor() as cur:
        branch = _branch(cur)
        if not branch:
            entries, total, total_pages, parents = [], 0, 1, []
            page = 1
        else:
            filters = ["e.branch_id = %s"]
            params = [branch["branch_id"]]
            if date_from:
                filters.append("e.entry_date >= %s")
                params.append(date_from)
            if date_to:
                filters.append("e.entry_date <= %s")
                params.append(date_to)
            where_clause = " AND ".join(filters)
            cur.execute(
                f"SELECT COUNT(*) AS total FROM journal_entries e WHERE {where_clause}",
                tuple(params),
            )
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                f"""SELECT e.journal_entry_id, e.entry_number, e.entry_date,
                           e.description, e.status, u.full_name AS created_by,
                           COALESCE(SUM(l.debit), 0) AS debit_total,
                           COALESCE(SUM(l.credit), 0) AS credit_total
                    FROM journal_entries e
                    JOIN users u ON u.user_id = e.created_by
                    LEFT JOIN journal_lines l ON l.journal_entry_id = e.journal_entry_id
                    WHERE {where_clause}
                    GROUP BY e.journal_entry_id, u.full_name
                    ORDER BY e.entry_date DESC, e.journal_entry_id DESC
                    LIMIT %s OFFSET %s""",
                tuple(params + [per_page, (page - 1) * per_page]),
            )
            entries = cur.fetchall()
            cur.execute(
                """SELECT account_id, account_code, account_name
                   FROM chart_of_accounts
                   WHERE is_active = TRUE AND (branch_id = %s OR branch_id IS NULL)
                   ORDER BY account_code LIMIT 500""",
                (branch["branch_id"],),
            )
            parents = cur.fetchall()

    return render_template(
        "finance/journals.html",
        branch=branch,
        entries=entries,
        accounts=parents,
        page=page,
        total=total,
        total_pages=total_pages,
        start_date=start_date,
        end_date=end_date,
        today=date.today().isoformat(),
    )


@finance_bp.post("/journals/<int:entry_id>/post")
@role_required("admin", "accountant")
def post_journal(entry_id):
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            if not branch:
                flash("Ask an administrator to assign you to an active branch first.", "error")
                return redirect(url_for("finance.dashboard"))
            cur.execute(
                """SELECT journal_entry_id, status
                   FROM journal_entries
                   WHERE journal_entry_id = %s AND branch_id = %s
                   FOR UPDATE""",
                (entry_id, branch["branch_id"]),
            )
            entry = cur.fetchone()
            if not entry:
                flash("Journal entry not found in the selected branch.", "error")
                return redirect(url_for("finance.journals"))
            if entry["status"] != "draft":
                flash("Only draft journal entries can be posted.", "error")
                return redirect(url_for("finance.journals"))
            cur.execute(
                """SELECT set_config('hms.user_id', %s, TRUE),
                          set_config('hms.username', %s, TRUE)""",
                (str(session["user_id"]), session.get("username", "")),
            )
            cur.execute(
                """UPDATE journal_entries SET status = 'posted'
                   WHERE journal_entry_id = %s AND branch_id = %s AND status = 'draft'""",
                (entry_id, branch["branch_id"]),
            )
            if cur.rowcount != 1:
                raise psycopg2.Error("Journal entry changed while being posted.")
            cur.connection.commit()
        flash("Journal entry posted.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to post finance journal entry")
        flash("The entry could not be posted. Confirm its lines balance and try again.", "error")
    return redirect(url_for("finance.journals"))


@finance_bp.route("/receivables", methods=["GET", "POST"])
@role_required("admin", "accountant")
def receivables():
    if request.method == "POST":
        try:
            patient_id = int(request.form.get("patient_id", ""))
            subtotal = _parse_amount(request.form.get("subtotal_amount", ""))
            tax_id = int(request.form["tax_id"]) if request.form.get("tax_id") else None
        except (ValueError, InvalidOperation) as error:
            flash(str(error) or "Enter a valid patient and invoice amount.", "error")
            return redirect(url_for("finance.receivables"))
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Ask an administrator to assign you to an active branch first.", "error")
                    return redirect(url_for("finance.dashboard"))
                cur.execute(
                    "SELECT patient_id FROM patients WHERE patient_id = %s AND branch_id = %s",
                    (patient_id, branch["branch_id"]),
                )
                if not cur.fetchone():
                    flash("Choose a patient registered in the active branch.", "error")
                    return redirect(url_for("finance.receivables"))
                rate = Decimal("0")
                if tax_id:
                    cur.execute(
                        """SELECT rate_percent FROM taxes
                           WHERE tax_id = %s AND is_active = TRUE
                             AND (branch_id = %s OR branch_id IS NULL)""",
                        (tax_id, branch["branch_id"]),
                    )
                    tax = cur.fetchone()
                    if not tax:
                        flash("Choose an active tax rate available to this branch.", "error")
                        return redirect(url_for("finance.receivables"))
                    rate = Decimal(tax["rate_percent"])
                tax_amount = (subtotal * rate / Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                total_amount = subtotal + tax_amount
                cur.execute(
                    """SELECT set_config('hms.user_id', %s, TRUE),
                              set_config('hms.username', %s, TRUE)""",
                    (str(session["user_id"]), session.get("username", "")),
                )
                invoice_number = f"AR-{date.today():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
                cur.execute(
                    """INSERT INTO billing
                           (patient_id, total_amount, payment_status, bill_date,
                            branch_id, tax_id, subtotal_amount, tax_amount, invoice_number)
                       VALUES (%s, %s, 'Pending', CURRENT_DATE, %s, %s, %s, %s, %s)""",
                    (patient_id, total_amount, branch["branch_id"], tax_id, subtotal, tax_amount, invoice_number),
                )
                cur.connection.commit()
            flash(f"Patient invoice {invoice_number} created.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to create patient invoice")
            flash("Patient invoice could not be saved.", "error")
        return redirect(url_for("finance.receivables"))

    page, per_page = _page_number(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        invoices, patients, taxes = [], [], []
        total, total_pages = 0, 1
        if branch:
            cur.execute(
                """SELECT patient_id, first_name, last_name FROM patients
                   WHERE branch_id = %s ORDER BY first_name, last_name LIMIT 500""",
                (branch["branch_id"],),
            )
            patients = cur.fetchall()
            cur.execute(
                """SELECT tax_id, tax_name, rate_percent FROM taxes
                   WHERE is_active = TRUE AND (branch_id = %s OR branch_id IS NULL)
                   ORDER BY tax_name LIMIT 500""",
                (branch["branch_id"],),
            )
            taxes = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS total FROM billing WHERE branch_id = %s", (branch["branch_id"],))
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT b.bill_id, b.invoice_number, b.bill_date, b.total_amount,
                          b.payment_status, p.first_name || ' ' || p.last_name AS patient_name,
                          COALESCE(SUM(pay.amount) FILTER (WHERE pay.status = 'posted'), 0) AS paid_amount
                   FROM billing b JOIN patients p USING (patient_id)
                   LEFT JOIN payments pay ON pay.bill_id = b.bill_id
                       AND pay.branch_id = b.branch_id AND pay.direction = 'incoming'
                   WHERE b.branch_id = %s
                   GROUP BY b.bill_id, p.first_name, p.last_name
                   ORDER BY b.bill_date DESC, b.bill_id DESC
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            invoices = cur.fetchall()
    return render_template(
        "finance/receivables.html", branch=branch, invoices=invoices,
        patients=patients, taxes=taxes, page=page, total=total, total_pages=total_pages,
        today=date.today().isoformat(),
    )


@finance_bp.post("/receivables/<int:bill_id>/payments")
@role_required("admin", "accountant")
def receive_payment(bill_id):
    try:
        amount = _parse_amount(request.form.get("amount", ""))
        payment_date = date.fromisoformat(request.form.get("payment_date", ""))
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("finance.receivables"))
    method = request.form.get("payment_method", "")
    if amount <= 0 or method not in {"cash", "bank_transfer", "card", "cheque", "other"}:
        flash("Choose a positive amount and valid payment method.", "error")
        return redirect(url_for("finance.receivables"))
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            if not branch:
                flash("No active branch is selected.", "error")
                return redirect(url_for("finance.dashboard"))
            cur.execute(
                """SELECT bill_id, total_amount, payment_status
                   FROM billing WHERE bill_id = %s AND branch_id = %s FOR UPDATE""",
                (bill_id, branch["branch_id"]),
            )
            bill = cur.fetchone()
            if not bill or bill["payment_status"] == "Cancelled":
                flash("Open invoice not found in the active branch.", "error")
                return redirect(url_for("finance.receivables"))
            cur.execute(
                """SELECT COALESCE(SUM(amount), 0) AS paid FROM payments
                   WHERE bill_id = %s AND branch_id = %s
                     AND direction = 'incoming' AND status = 'posted'""",
                (bill_id, branch["branch_id"]),
            )
            paid = Decimal(cur.fetchone()["paid"])
            remaining = Decimal(bill["total_amount"]) - paid
            if bill["payment_status"] == "Paid" or amount > remaining:
                flash("Payment cannot exceed the remaining invoice balance.", "error")
                return redirect(url_for("finance.receivables"))
            cur.execute(
                """SELECT set_config('hms.user_id', %s, TRUE),
                          set_config('hms.username', %s, TRUE)""",
                (str(session["user_id"]), session.get("username", "")),
            )
            number = f"PAY-{date.today():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
            cur.execute(
                """INSERT INTO payments
                       (branch_id, payment_number, direction, bill_id, amount,
                        payment_date, payment_method, status, recorded_by)
                   VALUES (%s, %s, 'incoming', %s, %s, %s, %s, 'posted', %s)""",
                (branch["branch_id"], number, bill_id, amount, payment_date, method, session["user_id"]),
            )
            status = "Paid" if amount == remaining else "Partially Paid"
            cur.execute(
                "UPDATE billing SET payment_status = %s WHERE bill_id = %s AND branch_id = %s",
                (status, bill_id, branch["branch_id"]),
            )
            cur.connection.commit()
        flash("Patient payment recorded.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to record patient payment")
        flash("Patient payment could not be recorded.", "error")
    return redirect(url_for("finance.receivables"))


@finance_bp.route("/taxes", methods=["GET", "POST"])
@role_required("admin", "accountant")
def taxes():
    if request.method == "POST":
        code = request.form.get("tax_code", "").strip().upper()
        name = request.form.get("tax_name", "").strip()
        try:
            rate = Decimal(request.form.get("rate_percent", ""))
        except (InvalidOperation, TypeError):
            rate = Decimal("-1")
        if (
            not code or len(code) > 30 or not name or len(name) > 100
            or not rate.is_finite() or rate < 0 or rate > 100
            or rate != rate.quantize(Decimal("0.0001"))
        ):
            flash("Enter a tax code, name and rate between 0 and 100 with up to 4 decimal places.", "error")
            return redirect(url_for("finance.taxes"))
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Select an active branch first.", "error")
                    return redirect(url_for("finance.dashboard"))
                cur.execute(
                    "INSERT INTO taxes (branch_id, tax_code, tax_name, rate_percent) VALUES (%s, %s, %s, %s)",
                    (branch["branch_id"], code, name, rate),
                )
                cur.connection.commit()
            flash("Tax rate created.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to create finance tax rate")
            flash("Tax rate could not be saved. Tax codes must be unique.", "error")
        return redirect(url_for("finance.taxes"))

    with db_cursor() as cur:
        branch = _branch(cur)
        tax_rows = []
        if branch:
            cur.execute(
                """SELECT tax_id, tax_code, tax_name, rate_percent, is_active, branch_id
                   FROM taxes WHERE branch_id = %s OR branch_id IS NULL ORDER BY tax_name""",
                (branch["branch_id"],),
            )
            tax_rows = cur.fetchall()
    return render_template("finance/taxes.html", branch=branch, taxes=tax_rows)


@finance_bp.post("/taxes/<int:tax_id>/toggle")
@role_required("admin", "accountant")
def toggle_tax(tax_id):
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            cur.execute(
                "UPDATE taxes SET is_active = NOT is_active WHERE tax_id = %s AND branch_id = %s",
                (tax_id, branch["branch_id"] if branch else None),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Branch tax rate was not found.", "error")
                return redirect(url_for("finance.taxes"))
            cur.connection.commit()
        flash("Tax rate status updated.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to update finance tax rate")
        flash("Tax rate status could not be updated.", "error")
    return redirect(url_for("finance.taxes"))


@finance_bp.get("/trial-balance")
@role_required("admin", "accountant")
def trial_balance():
    try:
        as_of = date.fromisoformat(request.args.get("as_of", date.today().isoformat()))
    except ValueError:
        flash("Choose a valid trial balance date.", "error")
        as_of = date.today()
    page, per_page = _page_number(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        rows, total, total_pages = [], 0, 1
        debit_total, credit_total = Decimal("0"), Decimal("0")
        if branch:
            cur.execute(
                """SELECT COUNT(*) AS total FROM chart_of_accounts
                   WHERE is_active = TRUE AND (branch_id = %s OR branch_id IS NULL)""",
                (branch["branch_id"],),
            )
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT a.account_id, a.account_code, a.account_name, a.account_type,
                          COALESCE(s.debits, 0) AS debits, COALESCE(s.credits, 0) AS credits,
                          GREATEST(COALESCE(s.debits, 0) - COALESCE(s.credits, 0), 0) AS debit_balance,
                          GREATEST(COALESCE(s.credits, 0) - COALESCE(s.debits, 0), 0) AS credit_balance
                   FROM chart_of_accounts a
                   LEFT JOIN (
                       SELECT l.account_id, SUM(l.debit) AS debits, SUM(l.credit) AS credits
                       FROM journal_lines l JOIN journal_entries e USING (journal_entry_id)
                       WHERE e.branch_id = %s AND e.status = 'posted' AND e.entry_date <= %s
                       GROUP BY l.account_id
                   ) s ON s.account_id = a.account_id
                   WHERE a.is_active = TRUE AND (a.branch_id = %s OR a.branch_id IS NULL)
                   ORDER BY a.account_code LIMIT %s OFFSET %s""",
                (branch["branch_id"], as_of, branch["branch_id"], per_page, (page - 1) * per_page),
            )
            rows = cur.fetchall()
            cur.execute(
                """SELECT COALESCE(SUM(l.debit), 0) AS debits, COALESCE(SUM(l.credit), 0) AS credits
                   FROM journal_lines l JOIN journal_entries e USING (journal_entry_id)
                   WHERE e.branch_id = %s AND e.status = 'posted' AND e.entry_date <= %s""",
                (branch["branch_id"], as_of),
            )
            totals = cur.fetchone()
            debit_total, credit_total = totals["debits"], totals["credits"]
    return render_template(
        "finance/trial_balance.html", branch=branch, rows=rows, as_of=as_of.isoformat(),
        debit_total=debit_total, credit_total=credit_total,
        page=page, total=total, total_pages=total_pages,
    )


@finance_bp.get("/balance-sheet")
@role_required("admin", "accountant")
def balance_sheet():
    try:
        as_of = date.fromisoformat(request.args.get("as_of", date.today().isoformat()))
    except ValueError:
        flash("Choose a valid balance sheet date.", "error")
        as_of = date.today()
    page, per_page = _page_number(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        rows = []
        totals = {"asset": Decimal("0"), "liability": Decimal("0"), "equity": Decimal("0")}
        total, total_pages = 0, 1
        if branch:
            cur.execute(
                """SELECT COUNT(*) AS total FROM chart_of_accounts
                   WHERE is_active = TRUE AND account_type IN ('asset', 'liability', 'equity')
                     AND (branch_id = %s OR branch_id IS NULL)""",
                (branch["branch_id"],),
            )
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            balance_sql = """SELECT l.account_id, SUM(l.debit) AS debits, SUM(l.credit) AS credits
                             FROM journal_lines l JOIN journal_entries e USING (journal_entry_id)
                             WHERE e.branch_id = %s AND e.status = 'posted' AND e.entry_date <= %s
                             GROUP BY l.account_id"""
            cur.execute(
                f"""SELECT a.account_code, a.account_name, a.account_type,
                           CASE WHEN a.account_type = 'asset'
                                THEN COALESCE(s.debits, 0) - COALESCE(s.credits, 0)
                                ELSE COALESCE(s.credits, 0) - COALESCE(s.debits, 0)
                           END AS balance
                    FROM chart_of_accounts a LEFT JOIN ({balance_sql}) s USING (account_id)
                    WHERE a.is_active = TRUE AND a.account_type IN ('asset', 'liability', 'equity')
                      AND (a.branch_id = %s OR a.branch_id IS NULL)
                    ORDER BY a.account_type, a.account_code LIMIT %s OFFSET %s""",
                (branch["branch_id"], as_of, branch["branch_id"], per_page, (page - 1) * per_page),
            )
            rows = cur.fetchall()
            cur.execute(
                f"""SELECT a.account_type,
                           SUM(CASE WHEN a.account_type = 'asset'
                                    THEN COALESCE(s.debits, 0) - COALESCE(s.credits, 0)
                                    ELSE COALESCE(s.credits, 0) - COALESCE(s.debits, 0)
                               END) AS balance
                    FROM chart_of_accounts a LEFT JOIN ({balance_sql}) s USING (account_id)
                    WHERE a.is_active = TRUE AND a.account_type IN ('asset', 'liability', 'equity')
                      AND (a.branch_id = %s OR a.branch_id IS NULL)
                    GROUP BY a.account_type""",
                (branch["branch_id"], as_of, branch["branch_id"]),
            )
            totals.update({row["account_type"]: row["balance"] for row in cur.fetchall()})
    return render_template(
        "finance/balance_sheet.html", branch=branch, rows=rows, totals=totals,
        as_of=as_of.isoformat(), page=page, total=total, total_pages=total_pages,
    )
