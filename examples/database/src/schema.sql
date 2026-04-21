-- Schema for Prototype Inventory Database
-- This represents the SSD-backed transactional workload

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    base_price DECIMAL(10, 2),
    sku_code VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stock_levels (
    product_id INTEGER REFERENCES products(id),
    warehouse_id INTEGER,
    quantity INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, warehouse_id)
);

-- Indexing for reporting performance during peak spikes
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_stock_product ON stock_levels(product_id);
