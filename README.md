# Single-Shop Inventory & Sales Manager

A Python (Flask) and PostgreSQL (Supabase-compatible) inventory and point-of-sale (POS) management application designed for single-shop retail operations. It tracks product catalogs, real-time stock levels, stock-in/stock-out audit trails, itemized sales with payment references, and daily sales reports.

## Features

* **Admin Authentication:** Session-based admin login backed by environment credentials (`admin_user`, `admin_pass`) and protected via a `@login_required` decorator.
* **Single-Shop Architecture:** Streamlined schema and routes tailored to one retail shop without multi-tenant overhead.
* **UUID Primary Keys:** Universally unique identifiers (`UUID`) generated via `gen_random_uuid()` across all tables.
* **Product Catalog & CRUD:** Add, edit, list, and soft-delete products (`is_active = FALSE`) while preserving historical sales and stock logs.
* **Atomic Stock Movements:** Record `STOCK_IN`, `STOCK_OUT`, and `ADJUSTMENT` operations using row-level database locks (`FOR UPDATE`) and full `stock_before` / `stock_after` audit trails.
* **POS Checkout (Form & JSON):** Record multi-item sales with `receipt_number`, `payment_method`, `tx_ref`, and `sold_at` timestamps while automatically deducting inventory and logging `STOCK_OUT` movements.
* **Daily Sales Reporting:** Filter sales summaries, payment method breakdowns, itemized transactions, and low-stock alerts by date (defaulting to the current date).

## Tech Stack

* **Backend:** Python 3, Flask
* **Database:** PostgreSQL 13+ / Supabase (via `psycopg2-binary` with `RealDictCursor`)
* **Configuration:** `python-dotenv`
* **frontend** `html5 css js`

## Project Structure

```text
.
├── app.py              # Flask application, auth, CRUD, stock & sales routes
├── schema.sql          # PostgreSQL database tables and indexes
├── .env                # Environment variables (DB URI, admin credentials)
├── README.md           # Project documentation
└── templates/          # Jinja2 HTML templates (to be added)
    ├── login.html
    ├── dashboard.html
    ├── products.html
    ├── stock_history.html
    └── new_sale.html
```

## Database Schema Overview

1. **`products`**: Stores SKU, name, description, `unit_price`, `cost_price`, `current_stock`, `reorder_level`, and `is_active`.
2. **`stock_movements`**: Immutable ledger of all `STOCK_IN`, `STOCK_OUT`, and `ADJUSTMENT` events with `quantity_delta`, `stock_before`, `stock_after`, `reason`, and `reference_code`.
3. **`sales`**: Transaction-level header storing `receipt_number`, `payment_method` (`CASH`, `CARD`, `MOBILE_MONEY`, `BANK_TRANSFER`, `OTHER`), `tx_ref`, `total_amount`, and `sold_at`.
4. **`sale_items`**: Line-item details for each sale (`sale_id`, `product_id`, `quantity`, `unit_price`, and auto-calculated `line_total`).

## Setup & Installation

### 1. Install Python Dependencies

```bash
pip install flask psycopg2-binary python-dotenv
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://postgres.[your-project-ref]:[your-password]@aws-0-[region].pooler.supabase.com:6543/postgres
admin_user=admin
admin_pass=your_strong_password
SECRET_KEY=your_random_flask_secret_key
```

### 3. Apply the Database Schema

Run `schema.sql` against your Supabase SQL Editor or local PostgreSQL database:

```bash
psql "$DATABASE_URL" -f schema.sql
```

### 4. Run the Application

```bash
python app.py
```

The server starts in debug mode at `http://127.0.0.1:5000`.

## Application Routes

All routes except `/login` require an authenticated admin session (`@login_required`).

| Method | Route | Description |
| :--- | :--- | :--- |
| `GET`, `POST` | `/login` | Admin login using `.env` (`admin_user` & `admin_pass`). |
| `GET` | `/logout` | Clears the active admin session. |
| `GET` | `/` | Daily sales report & dashboard (`?date=YYYY-MM-DD`, defaults to today), payment breakdown, and low-stock alerts. |
| `GET` | `/products` | Lists all active products in the shop. |
| `POST` | `/products/add` | Creates a product and logs an initial `STOCK_IN` movement if `current_stock > 0`. |
| `POST` | `/products/<uuid:product_id>/edit` | Updates product details, pricing, and reorder threshold. |
| `POST` | `/products/<uuid:product_id>/delete` | Soft-deletes a product (`is_active = FALSE`). |
| `POST` | `/stock/move` | Records `STOCK_IN`, `STOCK_OUT`, or `ADJUSTMENT` with row locking (`FOR UPDATE`). |
| `GET` | `/stock/history` | Displays the latest 200 stock movements across all products. |
| `GET`, `POST` | `/sales/new` | Renders checkout or records a multi-item sale (supports both HTML form arrays and JSON). |

## API Checkout Payload Example (`POST /sales/new`)

In addition to standard HTML form submissions (`product_id[]` and `quantity[]`), `/sales/new` accepts `application/json` requests:

```json
{
  "payment_method": "MOBILE_MONEY",
  "tx_ref": "TXN-20261126-8841",
  "receipt_number": "RCP-20261126-001",
  "items": [
    {
      "product_id": "550e8400-e29b-41d4-a716-446655440000",
      "quantity": 2
    }
  ]
}
```
