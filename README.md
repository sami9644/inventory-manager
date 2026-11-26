# Shop Inventory & Sales Manager

Single-shop inventory and point-of-sale tracking backend schema for PostgreSQL, built around UUID primary keys, stock movement audits (`STOCK_IN`, `STOCK_OUT`, `ADJUSTMENT`), sales headers (`payment_method`, `tx_ref`, `sold_at`), and line-item breakdowns.

## Database Schema

* `products`: Single-shop catalog with `sku`, `unit_price`, `cost_price`, `current_stock`, and `reorder_level`.
* `stock_movements`: Audit log of stock-in, stock-out, and adjustment deltas with `stock_before` and `stock_after` snapshots.
* `sales`: Checkout records storing `receipt_number`, `payment_method`, `tx_ref`, `total_amount`, and `sold_at`.
* `sale_items`: Line items linking each `sale_id` and `product_id` with `quantity`, `unit_price`, and generated `line_total`.

## Setup

1. Create a PostgreSQL database and load the schema:
   ```bash
   createdb shop_inventory
   psql -d shop_inventory -f schema.sql
