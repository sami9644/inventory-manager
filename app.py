import os
from functools import wraps
from datetime import datetime, date
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, session, redirect, url_for, render_template, flash, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-shop-key-change-me")

# Supabase PostgreSQL Connection URI (e.g., postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres)
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_USER = os.getenv("admin_user", "admin")
ADMIN_PASS = os.getenv("admin_pass", "admin123")


def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# --- AUTH ROUTES ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            session["admin_user"] = username
            return redirect(url_for("dashboard"))

        flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- DASHBOARD & DAILY SALES REPORT ---

@app.route("/")
@login_required
def dashboard():
    report_date_str = request.args.get("date")
    if report_date_str:
        report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
    else:
        report_date = date.today()

    conn = get_db()
    cur = conn.cursor()
    try:
        # Daily sales summary
        cur.execute("""
            SELECT 
                COUNT(id) AS total_transactions,
                COALESCE(SUM(total_amount), 0) AS total_revenue
            FROM sales
            WHERE DATE(sold_at) = %s
        """, (report_date,))
        summary = cur.fetchone()

        # Breakdown by payment method for the selected day
        cur.execute("""
            SELECT 
                payment_method,
                COUNT(id) AS tx_count,
                SUM(total_amount) AS amount
            FROM sales
            WHERE DATE(sold_at) = %s
            GROUP BY payment_method
        """, (report_date,))
        payment_breakdown = cur.fetchall()

        # Detailed sales & sold items for the selected day
        cur.execute("""
            SELECT 
                s.id AS sale_id,
                s.receipt_number,
                s.payment_method,
                s.tx_ref,
                s.total_amount,
                s.sold_at,
                p.name AS product_name,
                p.sku,
                si.quantity,
                si.unit_price,
                si.line_total
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            WHERE DATE(s.sold_at) = %s
            ORDER BY s.sold_at DESC
        """, (report_date,))
        daily_sales = cur.fetchall()

        # Low stock alert items
        cur.execute("""
            SELECT * FROM products
            WHERE is_active = TRUE AND current_stock <= reorder_level
            ORDER BY current_stock ASC
        """)
        low_stock = cur.fetchall()

    finally:
        cur.close()
        conn.close()

    return render_template(
        "dashboard.html",
        report_date=report_date,
        summary=summary,
        payment_breakdown=payment_breakdown,
        daily_sales=daily_sales,
        low_stock=low_stock
    )


# --- PRODUCTS CRUD ---

@app.route("/products")
@login_required
def list_products():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM products WHERE is_active = TRUE ORDER BY created_at DESC")
        products = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return render_template("products.html", products=products)


@app.route("/products/add", methods=["POST"])
@login_required
def add_product():
    sku = request.form.get("sku", "").strip()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    unit_price = float(request.form.get("unit_price", 0))
    cost_price = float(request.form.get("cost_price", 0))
    initial_stock = int(request.form.get("current_stock", 0))
    reorder_level = int(request.form.get("reorder_level", 5))

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO products (sku, name, description, unit_price, cost_price, current_stock, reorder_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (sku, name, description, unit_price, cost_price, initial_stock, reorder_level))
        product_id = cur.fetchone()["id"]

        if initial_stock > 0:
            cur.execute("""
                INSERT INTO stock_movements (product_id, movement_type, quantity_delta, stock_before, stock_after, reason)
                VALUES (%s, 'STOCK_IN', %s, 0, %s, 'Initial stock on product creation')
            """, (product_id, initial_stock, initial_stock))

        conn.commit()
        flash("Product added.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error adding product: {e}", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("list_products"))


@app.route("/products/<uuid:product_id>/edit", methods=["POST"])
@login_required
def edit_product(product_id):
    sku = request.form.get("sku", "").strip()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    unit_price = float(request.form.get("unit_price", 0))
    cost_price = float(request.form.get("cost_price", 0))
    reorder_level = int(request.form.get("reorder_level", 5))

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE products
            SET sku = %s, name = %s, description = %s, unit_price = %s,
                cost_price = %s, reorder_level = %s, updated_at = NOW()
            WHERE id = %s
        """, (sku, name, description, unit_price, cost_price, reorder_level, str(product_id)))
        conn.commit()
        flash("Product updated.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating product: {e}", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("list_products"))


@app.route("/products/<uuid:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        # Soft delete to preserve historical sales & stock movement foreign keys
        cur.execute("UPDATE products SET is_active = FALSE, updated_at = NOW() WHERE id = %s", (str(product_id),))
        conn.commit()
        flash("Product removed.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting product: {e}", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("list_products"))


# --- STOCK IN / STOCK OUT ---

@app.route("/stock/move", methods=["POST"])
@login_required
def stock_move():
    product_id = request.form.get("product_id")
    movement_type = request.form.get("movement_type")  # 'STOCK_IN', 'STOCK_OUT', or 'ADJUSTMENT'
    quantity = int(request.form.get("quantity", 0))
    reason = request.form.get("reason", "").strip()
    reference_code = request.form.get("reference_code", "").strip() or None

    if quantity <= 0:
        flash("Quantity must be greater than zero.", "error")
        return redirect(url_for("list_products"))

    conn = get_db()
    cur = conn.cursor()
    try:
        # Lock product row to prevent race conditions
        cur.execute("SELECT current_stock FROM products WHERE id = %s FOR UPDATE", (product_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Product not found.")

        stock_before = row["current_stock"]
        delta = quantity if movement_type == "STOCK_IN" else -quantity
        stock_after = stock_before + delta

        if stock_after < 0:
            raise ValueError("Insufficient stock for stock out.")

        cur.execute("""
            UPDATE products
            SET current_stock = %s, updated_at = NOW()
            WHERE id = %s
        """, (stock_after, product_id))

        cur.execute("""
            INSERT INTO stock_movements (product_id, movement_type, quantity_delta, stock_before, stock_after, reason, reference_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (product_id, movement_type, delta, stock_before, stock_after, reason, reference_code))

        conn.commit()
        flash(f"{movement_type} recorded.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Stock update failed: {e}", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("list_products"))


@app.route("/stock/history")
@login_required
def stock_history():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT sm.*, p.name AS product_name, p.sku
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            ORDER BY sm.created_at DESC
            LIMIT 200
        """)
        movements = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return render_template("stock_history.html", movements=movements)


# --- SALES (CHECKOUT & RECORDING SOLD ITEMS) ---

@app.route("/sales/new", methods=["GET", "POST"])
@login_required
def create_sale():
    if request.method == "GET":
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM products WHERE is_active = TRUE AND current_stock > 0 ORDER BY name ASC")
            products = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        return render_template("new_sale.html", products=products)

    # Expects JSON or form arrays: product_ids[], quantities[]
    data = request.get_json(silent=True) or request.form
    payment_method = data.get("payment_method", "CASH").upper()
    tx_ref = (data.get("tx_ref") or "").strip() or None
    receipt_number = (data.get("receipt_number") or "").strip() or f"RCP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    sold_at = data.get("sold_at") or datetime.now()

    if request.is_json:
        items = data.get("items", [])  # [{"product_id": "...", "quantity": 2}, ...]
    else:
        p_ids = request.form.getlist("product_id[]")
        qtys = request.form.getlist("quantity[]")
        items = [{"product_id": pid, "quantity": int(q)} for pid, q in zip(p_ids, qtys) if int(q) > 0]

    if not items:
        return jsonify({"error": "No items selected"}), 400 if request.is_json else redirect(url_for("create_sale"))

    conn = get_db()
    cur = conn.cursor()
    try:
        total_amount = 0
        prepared_items = []

        # Validate stock and calculate totals
        for item in items:
            pid = item["product_id"]
            qty = int(item["quantity"])

            cur.execute("SELECT id, name, unit_price, current_stock FROM products WHERE id = %s FOR UPDATE", (pid,))
            prod = cur.fetchone()
            if not prod:
                raise ValueError(f"Product {pid} not found.")
            if prod["current_stock"] < qty:
                raise ValueError(f"Insufficient stock for {prod['name']} (Available: {prod['current_stock']}).")

            unit_price = prod["unit_price"]
            total_amount += unit_price * qty
            prepared_items.append({
                "product_id": pid,
                "quantity": qty,
                "unit_price": unit_price,
                "stock_before": prod["current_stock"],
                "stock_after": prod["current_stock"] - qty
            })

        # Insert Sale Header
        cur.execute("""
            INSERT INTO sales (receipt_number, payment_method, tx_ref, total_amount, sold_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (receipt_number, payment_method, tx_ref, total_amount, sold_at))
        sale_id = cur.fetchone()["id"]

        # Insert Sale Items, deduct stock, and log STOCK_OUT movement
        for item in prepared_items:
            cur.execute("""
                INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
            """, (sale_id, item["product_id"], item["quantity"], item["unit_price"]))

            cur.execute("""
                UPDATE products SET current_stock = %s, updated_at = NOW() WHERE id = %s
            """, (item["stock_after"], item["product_id"]))

            cur.execute("""
                INSERT INTO stock_movements (product_id, movement_type, quantity_delta, stock_before, stock_after, reason, reference_code)
                VALUES (%s, 'STOCK_OUT', %s, %s, %s, 'Item sold', %s)
            """, (item["product_id"], -item["quantity"], item["stock_before"], item["stock_after"], receipt_number))

        conn.commit()

        if request.is_json:
            return jsonify({"message": "Sale recorded", "sale_id": str(sale_id), "receipt_number": receipt_number}), 201

        flash(f"Sale recorded ({receipt_number}).", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        conn.rollback()
        if request.is_json:
            return jsonify({"error": str(e)}), 400
        flash(f"Sale failed: {e}", "error")
        return redirect(url_for("create_sale"))
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    app.run(debug=True)