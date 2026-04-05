-- Drop tables if they exist (order respects foreign keys)
DROP TABLE IF EXISTS sale_items;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS purchase_items;
DROP TABLE IF EXISTS purchases;
DROP TABLE IF EXISTS stock;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS leaves_permissions;
DROP TABLE IF EXISTS salary_advances;
DROP TABLE IF EXISTS worker_attendance;
DROP TABLE IF EXISTS workers;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS suppliers;

-- 1. Customers
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    email TEXT,
    gender TEXT CHECK(gender IN ('M','F','O')),
    city TEXT NOT NULL,
    registration_date TEXT NOT NULL,      -- ISO date YYYY-MM-DD
    total_spent REAL DEFAULT 0
);

-- 2. Workers
CREATE TABLE workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('sales','cashier','manager')),
    salary REAL NOT NULL,
    joining_date TEXT NOT NULL
);

-- 3. Worker Attendance
CREATE TABLE worker_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    check_in TEXT,      -- HH:MM
    check_out TEXT,
    status TEXT CHECK(status IN ('Present','Half-Day','Leave','Absent')),
    FOREIGN KEY (worker_id) REFERENCES workers(id),
    UNIQUE(worker_id, date)
);

-- 4. Salary Advances
CREATE TABLE salary_advances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    reason TEXT,
    date TEXT NOT NULL,
    repaid BOOLEAN DEFAULT 0,
    FOREIGN KEY (worker_id) REFERENCES workers(id)
);

-- 5. Leaves / Permissions
CREATE TABLE leaves_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    type TEXT CHECK(type IN ('Leave','Permission')),
    reason TEXT,
    status TEXT CHECK(status IN ('Approved','Pending','Rejected')) DEFAULT 'Approved',
    FOREIGN KEY (worker_id) REFERENCES workers(id)
);

-- 6. Products
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('Men','Women','Kids','Wedding')),
    subcategory TEXT,                     -- e.g., Shirt, Trousers, Saree
    brand TEXT,
    size TEXT,
    color TEXT,
    cost_price REAL NOT NULL,             -- current cost price
    selling_price REAL NOT NULL,          -- current selling price
    created_at TEXT NOT NULL
);

-- 7. Stock
CREATE TABLE stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE,
    quantity INTEGER NOT NULL DEFAULT 0,
    last_updated TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- 8. Suppliers
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    city TEXT
);

-- 9. Purchases
CREATE TABLE purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    purchase_date TEXT NOT NULL,
    invoice_no TEXT NOT NULL UNIQUE,
    total_amount REAL NOT NULL,
    transport_cost REAL DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- 10. Purchase Items
CREATE TABLE purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    cost_price REAL NOT NULL,            -- actual cost at purchase
    total_cost REAL GENERATED ALWAYS AS (quantity * cost_price) STORED,
    FOREIGN KEY (purchase_id) REFERENCES purchases(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- 11. Sales
CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,                 -- NULL allowed for walk-in customers
    worker_id INTEGER NOT NULL,
    sale_date TEXT NOT NULL,
    sale_time TEXT NOT NULL,
    total_amount REAL NOT NULL,
    payment_type TEXT NOT NULL CHECK(payment_type IN ('Cash','UPI','Card')),
    discount_total REAL DEFAULT 0,
    profit_total REAL,                   -- can be computed but stored for speed
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (worker_id) REFERENCES workers(id)
);

-- 12. Sale Items
CREATE TABLE sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    cost_price REAL NOT NULL,            -- actual cost at sale time
    selling_price REAL NOT NULL,         -- actual selling price (after any markdown)
    discount_percent REAL DEFAULT 0,
    final_price REAL GENERATED ALWAYS AS (quantity * selling_price * (1 - discount_percent/100)) STORED,
    FOREIGN KEY (sale_id) REFERENCES sales(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);