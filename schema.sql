CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('sales','cashier','manager')),
    salary REAL NOT NULL,
    joining_date TEXT NOT NULL
);
CREATE TABLE "attendance" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    check_in TEXT,      -- HH:MM
    check_out TEXT,
    status TEXT CHECK(status IN ('Present','Half-Day','Leave','Absent')),
    FOREIGN KEY (worker_id) REFERENCES workers(id),
    UNIQUE(worker_id, date)
);
CREATE TABLE salary_advances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    reason TEXT,
    date TEXT NOT NULL,
    repaid BOOLEAN DEFAULT 0,
    FOREIGN KEY (worker_id) REFERENCES workers(id)
);
CREATE TABLE "leaves" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    type TEXT CHECK(type IN ('Leave','Permission')),
    reason TEXT,
    status TEXT CHECK(status IN ('Approved','Pending','Rejected')) DEFAULT 'Approved',
    FOREIGN KEY (worker_id) REFERENCES workers(id)
);
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
CREATE TABLE stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE,
    quantity INTEGER NOT NULL DEFAULT 0,
    last_updated TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_name TEXT,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    city TEXT
);
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
CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,                 -- NULL allowed for walk-in customers
    worker_id INTEGER NOT NULL,
    sale_date TEXT NOT NULL,
    sale_time TEXT NOT NULL,
    total_amount REAL NOT NULL,
    payment_type TEXT NOT NULL CHECK(payment_type IN ('Cash','UPI','Card')),
    discount_total REAL DEFAULT 0,
    profit_total REAL, date_time TEXT,                   -- can be computed but stored for speed
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (worker_id) REFERENCES workers(id)
);
CREATE TABLE sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    cost_price REAL NOT NULL,            -- actual cost at sale time
    selling_price REAL NOT NULL,         -- actual selling price (after any markdown)
    discount REAL DEFAULT 0,
    final_price REAL GENERATED ALWAYS AS (quantity * selling_price * (1 - discount/100)) STORED,
    FOREIGN KEY (sale_id) REFERENCES sales(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
CREATE TABLE "customers" (
            id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT,
            email TEXT,
            city TEXT,
            gender TEXT,
            total_spent REAL
        );