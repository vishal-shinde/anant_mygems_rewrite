BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    role_id INT NOT NULL REFERENCES roles(role_id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    customer_name VARCHAR(200) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(200),
    address TEXT,
    city VARCHAR(100),
    gst_no VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vendors (
    vendor_id SERIAL PRIMARY KEY,
    vendor_name VARCHAR(200) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(200),
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS metal_purchases (
    purchase_id SERIAL PRIMARY KEY,
    vendor_id INT REFERENCES vendors(vendor_id),
    vendor_name VARCHAR(200),
    metal_type VARCHAR(50) NOT NULL,
    quantity NUMERIC(18,3) NOT NULL DEFAULT 0,
    rate NUMERIC(18,2) NOT NULL DEFAULT 0,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    purchase_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchases (
    purchase_id SERIAL PRIMARY KEY,
    vendor_id INT REFERENCES vendors(vendor_id),
    vendor_name VARCHAR(200),
    metal_type VARCHAR(50) NOT NULL,
    quantity NUMERIC(18,3) NOT NULL DEFAULT 0,
    rate NUMERIC(18,2) NOT NULL DEFAULT 0,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    purchase_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gold_jewelry (
    jewelry_id SERIAL PRIMARY KEY,
    lot_no VARCHAR(100) NOT NULL UNIQUE,
    item_code VARCHAR(100),
    metal_type VARCHAR(20) NOT NULL DEFAULT 'gold',
    current_weight NUMERIC(18,3) NOT NULL DEFAULT 0,
    purity NUMERIC(5,2),
    status VARCHAR(50) NOT NULL DEFAULT 'MFG',
    purchase_id INT REFERENCES metal_purchases(purchase_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver_jewelry (
    jewelry_id SERIAL PRIMARY KEY,
    lot_no VARCHAR(100) NOT NULL UNIQUE,
    item_code VARCHAR(100),
    metal_type VARCHAR(20) NOT NULL DEFAULT 'silver',
    current_weight NUMERIC(18,3) NOT NULL DEFAULT 0,
    purity NUMERIC(5,2),
    status VARCHAR(50) NOT NULL DEFAULT 'MFG',
    purchase_id INT REFERENCES metal_purchases(purchase_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id) ON DELETE RESTRICT,
    order_status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    total_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_paid NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_balance NUMERIC(18,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES sales_orders(order_id) ON DELETE CASCADE,
    item_code VARCHAR(100),
    lot_no VARCHAR(100),
    metal_type VARCHAR(50),
    sold_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    paid_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    balance_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    item_status VARCHAR(50) NOT NULL DEFAULT 'PENDING_STOCK',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_payments (
    payment_id SERIAL PRIMARY KEY,
    order_id INT REFERENCES sales_orders(order_id) ON DELETE CASCADE,
    order_item_id INT REFERENCES sales_order_items(order_item_id) ON DELETE CASCADE,
    payment_mode VARCHAR(50) NOT NULL DEFAULT 'CASH',
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    paid_on TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id SERIAL PRIMARY KEY,
    job_code VARCHAR(100) NOT NULL UNIQUE,
    customer_id INT REFERENCES customers(customer_id),
    customer_name VARCHAR(200),
    job_type VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    assigned_to VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_assignments (
    assignment_id SERIAL PRIMARY KEY,
    job_id INT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    employee_name VARCHAR(200),
    assigned_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'ASSIGNED',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS expenses (
    expense_id SERIAL PRIMARY KEY,
    expense_type VARCHAR(100) NOT NULL,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    expense_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(customer_name);
CREATE INDEX IF NOT EXISTS idx_sales_orders_customer_id ON sales_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_order_items_order_id ON sales_order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_sales_order_items_status ON sales_order_items(item_status);
CREATE INDEX IF NOT EXISTS idx_sales_payments_order_id ON sales_payments(order_id);
CREATE INDEX IF NOT EXISTS idx_gold_jewelry_status ON gold_jewelry(status);
CREATE INDEX IF NOT EXISTS idx_silver_jewelry_status ON silver_jewelry(status);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_job_assignments_job_id ON job_assignments(job_id);

INSERT INTO roles (role_name, description)
VALUES
    ('Admin', 'System administrator'),
    ('Manager', 'Operations manager'),
    ('Cashier', 'Sales and payment handling'),
    ('Staff', 'General staff access')
ON CONFLICT (role_name) DO NOTHING;

INSERT INTO users (username, password_hash, full_name, role_id, is_active)
VALUES (
    'admin',
    '$2b$12$//7wrEPVKPIu88kSEhp/bu29gbhcN4uWGSu3FGgsSIFA.2m/QQiZq',
    'System Admin',
    (SELECT role_id FROM roles WHERE role_name = 'Admin'),
    TRUE
)
ON CONFLICT (username) DO NOTHING;

COMMIT;
