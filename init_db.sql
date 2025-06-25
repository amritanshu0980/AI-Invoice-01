-- Users table to store user information
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'user')) DEFAULT 'user',
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

-- Products table to store product catalog
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    gst_rate REAL DEFAULT 18.0,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

-- Trigger to update updated_at timestamp in products table
CREATE TRIGGER IF NOT EXISTS update_products_updated_at
AFTER UPDATE ON products
FOR EACH ROW
BEGIN
    UPDATE products SET updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now') WHERE id = OLD.id;
END;

-- Invoices table to store invoice details
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    discount REAL DEFAULT 0.0,
    final_amount REAL NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Invoice Items table to store items in each invoice
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    price_at_time REAL NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- Cart Items table to store items in a user's cart
CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    added_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- Activities table to log user and admin activities
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Charges table to store additional charges (e.g., service, handling)
CREATE TABLE IF NOT EXISTS charges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount REAL NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

-- Trigger to update updated_at timestamp in charges table
CREATE TRIGGER IF NOT EXISTS update_charges_updated_at
AFTER UPDATE ON charges
FOR EACH ROW
BEGIN
    UPDATE charges SET updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now') WHERE id = OLD.id;
END;

-- Insert a default admin user for testing
INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin');
-- Insert a default regular user for testing
INSERT INTO users (username, password, role) VALUES ('user1', 'user123', 'user');
-- Insert some sample products
INSERT INTO products (name, price, gst_rate) VALUES
    ('Product A', 500.00, 18.0),
    ('Product B', 750.00, 18.0),
    ('Product C', 300.00, 18.0);
-- Insert a sample charge
INSERT INTO charges (name, amount) VALUES ('Service Charge', 50.00);