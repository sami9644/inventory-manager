# Single-Shop Inventory & Sales Manager

A PostgreSQL-backed inventory and point-of-sale (POS) management system designed specifically for single-shop retail operations. It tracks product catalogs, real-time stock levels, stock-in/stock-out audit trails, and itemized sales transactions with payment references.

## Features

* **Single-Shop Architecture:** Streamlined schema without multi-tenant or multi-branch overhead.
* **UUID Primary Keys:** Universally unique identifiers (`UUID`) generated via `gen_random_uuid()` for every record across all tables.
* **Product Catalog & Stock Tracking:** Manage SKUs, pricing (unit and cost price), active status, current inventory counts, and low-stock reorder thresholds.
* **Complete Stock Audit Trail:** Every inventory addition (`STOCK_IN`), deduction (`STOCK_OUT`), or manual correction (`ADJUSTMENT`) logs `stock_before`, `quantity_delta`, and `stock_after`.
* **Sales & Payment Tracking:** Record receipt numbers, timestamps (`sold_at`), payment methods (`CASH`, `CARD`, `MOBILE_MONEY`, `BANK_TRANSFER`, `OTHER`), and unique transaction references (`tx_ref`), linked to individual sold items.

## Database Schema Overview

The PostgreSQL schema consists of four core tables:

1. **`products`**: Stores the shop's item catalog, pricing, reorder levels, and `current_stock`.
2. **`stock_movements`**: Immutable ledger of all stock-in, stock-out, and adjustment events tied to a `product_id`.
3. **`sales`**: Stores transaction-level metadata including `receipt_number`, `payment_method`, `tx_ref`, `total_amount`, and `sold_at`.
4. **`sale_items`**: Line-item details for each sale (`sale_id`, `product_id`, `quantity`, `unit_price`, and auto-calculated `line_total`).

## Prerequisites

* **PostgreSQL 13+** (includes built-in `gen_random_uuid()`; for PostgreSQL 12 or older, the schema enables the `pgcrypto` extension).
* A PostgreSQL client (`psql`, pgAdmin, DBeaver, etc.) or backend runtime (Node.js, Python, Go, etc.).

## Getting Started

### 1. Create the Database
```bash
createdb shop_inventory
```

### 2. Apply the Schema
Save the schema SQL to `schema.sql` and run:
```bash
psql -d shop_inventory -f schema.sql
```

## Example Usage

### Add a Product
```sql
INSERT INTO products (sku, name, description, unit_price, cost_price, current_stock, reorder_level)
VALUES ('SKU-001', 'Wireless Mouse', '2.4GHz ergonomic wireless mouse', 25.00, 14.50, 50, 10)
RETURNING id, sku, name, current_stock;
```

### Record Stock In (Restock)
```sql
BEGIN;

UPDATE products
SET current_stock = current_stock + 20, updated_at = NOW()
WHERE sku = 'SKU-001';

INSERT INTO stock_movements (product_id, movement_type, quantity_delta, stock_before, stock_after, reason, reference_code)
SELECT id, 'STOCK_IN', 20, current_stock - 20, current_stock, 'Supplier restock', 'PO-2026-001'
FROM products
WHERE sku = 'SKU-001';

COMMIT;
```

### Record a Sale & Deduct Stock
```sql
BEGIN;

-- 1. Create the sale header
WITH new_sale AS (
    INSERT INTO sales (receipt_number, payment_method, tx_ref, total_amount)
    VALUES ('RCP-1001', 'MOBILE_MONEY', 'TXN-987654321', 50.00)
    RETURNING id
),
-- 2. Insert line items
inserted_items AS (
    INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
    SELECT new_sale.id, p.id, 2, p.unit_price
    FROM new_sale, products p
    WHERE p.sku = 'SKU-001'
    RETURNING product_id, quantity
)
-- 3. Update product stock
UPDATE products p
SET current_stock = p.current_stock - i.quantity, updated_at = NOW()
FROM inserted_items i
WHERE p.id = i.product_id;

-- 4. Log stock out movement
INSERT INTO stock_movements (product_id, movement_type, quantity_delta, stock_before, stock_after, reason, reference_code)
SELECT id, 'STOCK_OUT', -2, current_stock + 2, current_stock, 'Customer sale', 'RCP-1001'
FROM products
WHERE sku = 'SKU-001';

COMMIT;
```

### Check Low-Stock Items
```sql
SELECT sku, name, current_stock, reorder_level
FROM products
WHERE is_active = TRUE AND current_stock <= reorder_level
ORDER BY current_stock ASC;
```

## Next Steps & Extensibility

* **Database Triggers:** Add PostgreSQL triggers on `sale_items` and `stock_movements` to automatically keep `products.current_stock` in sync without manual transaction steps.
* **Reporting Views:** Create SQL views for daily revenue by `payment_method`, top-selling items, and profit margins (`unit_price - cost_price`).
