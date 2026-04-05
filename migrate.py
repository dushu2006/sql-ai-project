import sqlite3
import shutil
import os

DB_PATH = "retail.db"
BACKUP_PATH = "retail.db.bak"

def migrate():
    # 1. Backup
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print("Backup created at", BACKUP_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")

    # 1. Migrate `sales`
    cur.execute('''
    CREATE TABLE sales_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        worker_id INTEGER NOT NULL,
        date_time TEXT NOT NULL,
        total_amount REAL NOT NULL,
        payment_type TEXT NOT NULL CHECK(payment_type IN ('Cash','UPI','Card')),
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
        FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE RESTRICT
    )
    ''')
    cur.execute('''
    INSERT INTO sales_new (id, customer_id, worker_id, date_time, total_amount, payment_type)
    SELECT id, customer_id, worker_id, 
           COALESCE(date_time, sale_date || ' ' || sale_time), 
           total_amount, payment_type 
    FROM sales
    ''')
    cur.execute("DROP TABLE sales")
    cur.execute("ALTER TABLE sales_new RENAME TO sales")

    # 2. Migrate `sale_items`
    cur.execute('''
    CREATE TABLE sale_items_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        cost_price REAL NOT NULL,
        selling_price REAL NOT NULL,
        discount REAL DEFAULT 0,
        final_price REAL GENERATED ALWAYS AS (quantity * selling_price * (1 - discount/100)) STORED,
        FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
    )
    ''')
    cur.execute('''
    INSERT INTO sale_items_new (id, sale_id, product_id, quantity, cost_price, selling_price, discount)
    SELECT id, sale_id, product_id, quantity, cost_price, selling_price, discount
    FROM sale_items
    ''')
    cur.execute("DROP TABLE sale_items")
    cur.execute("ALTER TABLE sale_items_new RENAME TO sale_items")

    # 3. Migrate `purchases` 
    cur.execute('''
    CREATE TABLE purchases_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL,
        purchase_date TEXT NOT NULL,
        invoice_no TEXT NOT NULL UNIQUE,
        total_amount REAL NOT NULL,
        transport_cost REAL DEFAULT 0,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'Received' CHECK(status IN ('Pending', 'In Transit', 'Received', 'Cancelled')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT
    )
    ''')
    try:
        cur.execute('''
        INSERT INTO purchases_new (id, supplier_id, purchase_date, invoice_no, total_amount, transport_cost, notes)
        SELECT id, supplier_id, purchase_date, invoice_no, total_amount, transport_cost, notes
        FROM purchases
        ''')
    except sqlite3.OperationalError as e:
        print("Note on purchases migrate:", e)
    
    cur.execute("DROP TABLE purchases")
    cur.execute("ALTER TABLE purchases_new RENAME TO purchases")

    # 4. Migrate `purchase_items`
    cur.execute('''
    CREATE TABLE purchase_items_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        cost_price REAL NOT NULL,
        total_cost REAL GENERATED ALWAYS AS (quantity * cost_price) STORED,
        FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
    )
    ''')
    cur.execute('''
    INSERT INTO purchase_items_new (id, purchase_id, product_id, quantity, cost_price)
    SELECT id, purchase_id, product_id, quantity, cost_price
    FROM purchase_items
    ''')
    cur.execute("DROP TABLE purchase_items")
    cur.execute("ALTER TABLE purchase_items_new RENAME TO purchase_items")

    # 5. Migrate `attendance`
    cur.execute('''
    CREATE TABLE attendance_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER NOT NULL,
        attendance_date TEXT NOT NULL,
        check_in TEXT,
        check_out TEXT,
        status TEXT CHECK(status IN ('Present','Half-Day','Leave','Absent')),
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE,
        UNIQUE(worker_id, attendance_date)
    )
    ''')
    cur.execute('''
    INSERT INTO attendance_new (id, worker_id, attendance_date, check_in, check_out, status)
    SELECT id, worker_id, date, check_in, check_out, status
    FROM attendance
    ''')
    cur.execute("DROP TABLE attendance")
    cur.execute("ALTER TABLE attendance_new RENAME TO attendance")

    # 6. Migrate `leaves`
    cur.execute('''
    CREATE TABLE leaves_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER NOT NULL,
        leave_start_date TEXT NOT NULL,
        leave_end_date TEXT NOT NULL,
        type TEXT CHECK(type IN ('Leave','Permission')),
        reason TEXT,
        status TEXT CHECK(status IN ('Approved','Pending','Rejected')) DEFAULT 'Approved',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE
    )
    ''')
    cur.execute('''
    INSERT INTO leaves_new (id, worker_id, leave_start_date, leave_end_date, type, reason, status)
    SELECT id, worker_id, start_date, end_date, type, reason, status
    FROM leaves
    ''')
    cur.execute("DROP TABLE leaves")
    cur.execute("ALTER TABLE leaves_new RENAME TO leaves")

    # 7. Migrate `customers` 
    cur.execute('''
    CREATE TABLE customers_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT UNIQUE,
        city TEXT,
        gender TEXT,
        total_spent REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cur.execute('''
    INSERT INTO customers_new (id, name, phone, email, city, gender, total_spent)
    SELECT id, name, phone, email, city, gender, total_spent
    FROM customers
    ''')
    cur.execute("DROP TABLE customers")
    cur.execute("ALTER TABLE customers_new RENAME TO customers")

    # 8. Migrate `suppliers`
    cur.execute('''
    CREATE TABLE suppliers_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact_name TEXT,
        phone TEXT NOT NULL,
        email TEXT UNIQUE,
        address TEXT,
        city TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cur.execute('''
    INSERT INTO suppliers_new (id, name, contact_name, phone, email, address, city)
    SELECT id, name, contact_name, phone, email, address, city
    FROM suppliers
    ''')
    cur.execute("DROP TABLE suppliers")
    cur.execute("ALTER TABLE suppliers_new RENAME TO suppliers")

    # 9. Stock triggers
    cur.execute("DROP TRIGGER IF EXISTS update_stock_after_purchase")
    cur.execute('''
    CREATE TRIGGER update_stock_after_purchase
    AFTER INSERT ON purchase_items
    BEGIN
        UPDATE stock
        SET quantity = quantity + NEW.quantity,
            last_updated = CURRENT_TIMESTAMP
        WHERE product_id = NEW.product_id;
    END;
    ''')

    cur.execute("DROP TRIGGER IF EXISTS update_stock_after_sale")
    cur.execute('''
    CREATE TRIGGER update_stock_after_sale
    AFTER INSERT ON sale_items
    BEGIN
        UPDATE stock
        SET quantity = quantity - NEW.quantity,
            last_updated = CURRENT_TIMESTAMP
        WHERE product_id = NEW.product_id;
    END;
    ''')

    conn.commit()
    conn.close()
    print("Migration successful.")

if __name__ == "__main__":
    migrate()
