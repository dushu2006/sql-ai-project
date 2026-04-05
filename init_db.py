import sqlite3
import random
import datetime
import uuid
import math

# ---------- Configuration ----------
DB_NAME = "retail.db"
START_DATE = datetime.date(2024, 1, 1)      # start of data (6+ months ago)
END_DATE = datetime.date(2025, 3, 31)       # end of data (today or recent)
NUM_CUSTOMERS = 800                         # between 500-1000
NUM_WORKERS = 70                            # between 50-100
NUM_PRODUCTS = 400                          # between 200-500
NUM_SALES = 35000                           # between 15000-50000

# Realistic Indian cities
CITIES = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Ahmedabad", "Chennai", "Kolkata", "Pune", "Jaipur", "Lucknow", "Nagpur", "Indore"]
GENDERS = ["M", "F", "O"]

# Product categories and subcategories
CATEGORIES = {
    "Men": ["Shirt", "Trousers", "Jeans", "T-Shirt", "Jacket", "Sweater", "Ethnic"],
    "Women": ["Saree", "Kurta", "Lehenga", "Top", "Jeans", "Dress", "Skirt"],
    "Kids": ["T-Shirt", "Shorts", "Frock", "Jeans", "Ethnic"],
    "Wedding": ["Bridal Lehenga", "Groom Sherwani", "Wedding Saree", "Jewelry Set"]
}
BRANDS = ["Allen Solly", "Peter England", "Louis Philippe", "Van Heusen", "Wrangler", "Levi's", "US Polo", "FabIndia", "Biba", "W for Women", "Mothercare", "Manyavar"]

SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
COLORS = ["Red", "Blue", "Green", "Black", "White", "Yellow", "Pink", "Purple", "Orange"]

# Roles and salaries
ROLES = {
    "sales": (15000, 25000),
    "cashier": (12000, 18000),
    "manager": (30000, 50000)
}

# Payment types distribution (weights)
PAYMENT_TYPES = ["Cash", "UPI", "Card"]
PAYMENT_WEIGHTS = [30, 50, 20]   # percentages

# Helper functions
def random_date(start, end):
    """Return a random date between start and end (inclusive)."""
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + datetime.timedelta(days=random_days)

def random_time():
    """Return a random time string (HH:MM) with bias towards evening (higher sales)."""
    # 40% sales in morning (9-12), 60% in evening (16-20)
    if random.random() < 0.6:
        hour = random.randint(16, 20)
    else:
        hour = random.randint(9, 12)
    minute = random.randint(0, 59)
    return f"{hour:02d}:{minute:02d}"

def indian_name(gender=None):
    """Return a random Indian name (first + last)."""
    first_names_m = ["Aarav", "Vihaan", "Vivaan", "Ananya", "Diya", "Arjun", "Sai", "Aditya", "Rohan", "Kabir", "Ishaan", "Shaurya", "Aryan", "Reyansh", "Dhruv"]
    first_names_f = ["Aadhya", "Ananya", "Diya", "Ishita", "Jhanvi", "Kavya", "Navya", "Pari", "Riya", "Saanvi", "Sara", "Tara", "Vedika", "Zara"]
    last_names = ["Sharma", "Verma", "Gupta", "Kumar", "Singh", "Reddy", "Patel", "Yadav", "Jha", "Mehta", "Choudhary", "Mishra", "Das", "Khan", "Nair"]
    if gender == "M":
        first = random.choice(first_names_m)
    elif gender == "F":
        first = random.choice(first_names_f)
    else:
        first = random.choice(first_names_m + first_names_f)
    last = random.choice(last_names)
    return f"{first} {last}"

def indian_phone():
    """Generate a 10-digit Indian mobile number (starts with 6-9)."""
    return f"{random.choice(['6','7','8','9'])}{random.randint(100000000, 999999999)}"

def indian_email(name):
    """Generate an email from name."""
    clean = name.lower().replace(" ", ".")
    return f"{clean}@example.com"

# ---------- Database connection ----------
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Create tables (executes the SQL schema)
with open("tables.sql", "r") as f:
    cursor.executescript(f.read())

# ---------- Generate Data ----------
print("Generating customers...")
customers = []
for _ in range(NUM_CUSTOMERS):
    gender = random.choice(GENDERS)
    name = indian_name(gender)
    phone = indian_phone()
    email = indian_email(name)
    city = random.choice(CITIES)
    reg_date = random_date(START_DATE, END_DATE - datetime.timedelta(days=30))
    customers.append((name, phone, email, gender, city, reg_date.isoformat()))
cursor.executemany("INSERT INTO customers (name, phone, email, gender, city, registration_date) VALUES (?,?,?,?,?,?)", customers)
conn.commit()
print(f"Inserted {len(customers)} customers.")

print("Generating workers...")
workers = []
worker_ids = []  # store for later references
for role, (min_sal, max_sal) in ROLES.items():
    num = NUM_WORKERS // len(ROLES) if role != "manager" else NUM_WORKERS // (len(ROLES)*2)  # fewer managers
    for _ in range(num):
        name = indian_name()
        salary = round(random.uniform(min_sal, max_sal), 2)
        join_date = random_date(START_DATE - datetime.timedelta(days=365), START_DATE)
        workers.append((name, role, salary, join_date.isoformat()))
# Ensure total workers count
while len(workers) < NUM_WORKERS:
    role = random.choice(list(ROLES.keys()))
    min_sal, max_sal = ROLES[role]
    name = indian_name()
    salary = round(random.uniform(min_sal, max_sal), 2)
    join_date = random_date(START_DATE - datetime.timedelta(days=365), START_DATE)
    workers.append((name, role, salary, join_date.isoformat()))
cursor.executemany("INSERT INTO workers (name, role, salary, joining_date) VALUES (?,?,?,?)", workers)
conn.commit()
# Fetch worker ids
cursor.execute("SELECT id FROM workers")
worker_ids = [row[0] for row in cursor.fetchall()]
print(f"Inserted {len(workers)} workers.")

print("Generating attendance, leaves, advances...")
# Generate attendance for each worker for each day in the date range
# But only for days after their joining date
attendance_data = []
leaves_data = []
advances_data = []
for worker_id in worker_ids:
    # Get worker's joining date
    cursor.execute("SELECT joining_date FROM workers WHERE id = ?", (worker_id,))
    join_date = datetime.date.fromisoformat(cursor.fetchone()[0])
    start_att = max(START_DATE, join_date)
    # For each day from start_att to END_DATE
    current_date = start_att
    while current_date <= END_DATE:
        # Determine status (80% present, 10% half-day, 10% leave)
        rand = random.random()
        if rand < 0.8:
            status = "Present"
            check_in = "09:00" if random.random() < 0.9 else f"{random.randint(8,10):02d}:{random.randint(0,59):02d}"
            check_out = "18:00" if random.random() < 0.9 else f"{random.randint(17,20):02d}:{random.randint(0,59):02d}"
        elif rand < 0.9:
            status = "Half-Day"
            check_in = "09:00"
            check_out = "13:00" if random.random() < 0.5 else "14:00"
        else:
            status = "Leave"
            check_in = None
            check_out = None
        attendance_data.append((worker_id, current_date.isoformat(), check_in, check_out, status))
        # If leave, also record in leaves_permissions
        if status == "Leave":
            leaves_data.append((worker_id, current_date.isoformat(), current_date.isoformat(), "Leave", "Annual leave", "Approved"))
        current_date += datetime.timedelta(days=1)
# Insert attendance
cursor.executemany("INSERT INTO worker_attendance (worker_id, date, check_in, check_out, status) VALUES (?,?,?,?,?)", attendance_data)
conn.commit()
print(f"Inserted {len(attendance_data)} attendance records.")

# Insert leaves (only those we flagged, plus some extra permissions)
cursor.executemany("INSERT INTO leaves_permissions (worker_id, start_date, end_date, type, reason, status) VALUES (?,?,?,?,?,?)", leaves_data)
# Add some random permissions (short leaves)
for worker_id in worker_ids:
    for _ in range(random.randint(0, 3)):
        start = random_date(START_DATE, END_DATE)
        end = start + datetime.timedelta(hours=random.randint(1, 4))
        reason = random.choice(["Doctor", "Personal", "Family"])
        leaves_data.append((worker_id, start.isoformat(), end.isoformat(), "Permission", reason, "Approved"))
cursor.executemany("INSERT INTO leaves_permissions (worker_id, start_date, end_date, type, reason, status) VALUES (?,?,?,?,?,?)", leaves_data)
conn.commit()
print(f"Inserted additional {len(leaves_data)} leaves/permissions.")

# Advances
for worker_id in worker_ids:
    # 30% workers have advances
    if random.random() < 0.3:
        amount = round(random.uniform(2000, 15000), 2)
        date = random_date(START_DATE, END_DATE)
        reason = random.choice(["Medical", "Wedding", "Education", "Emergency"])
        advances_data.append((worker_id, amount, reason, date.isoformat(), 0))
cursor.executemany("INSERT INTO salary_advances (worker_id, amount, reason, date, repaid) VALUES (?,?,?,?,?)", advances_data)
conn.commit()
print(f"Inserted {len(advances_data)} advances.")

print("Generating products...")
products = []
for cat, subcats in CATEGORIES.items():
    for sub in subcats:
        num_prod = NUM_PRODUCTS // sum(len(v) for v in CATEGORIES.values())  # roughly distribute
        for _ in range(num_prod):
            brand = random.choice(BRANDS)
            size = random.choice(SIZES)
            color = random.choice(COLORS)
            cost_price = round(random.uniform(200, 5000), 2)
            # Markup between 1.5x and 3x
            selling_price = round(cost_price * random.uniform(1.5, 3.0), 2)
            name = f"{brand} {sub} {color} {size}"
            created_at = random_date(START_DATE - datetime.timedelta(days=180), START_DATE).isoformat()
            products.append((name, cat, sub, brand, size, color, cost_price, selling_price, created_at))
# Insert products
cursor.executemany("INSERT INTO products (name, category, subcategory, brand, size, color, cost_price, selling_price, created_at) VALUES (?,?,?,?,?,?,?,?,?)", products)
conn.commit()
# Fetch product ids
cursor.execute("SELECT id, cost_price, selling_price FROM products")
product_rows = cursor.fetchall()
product_ids = [row[0] for row in product_rows]
product_cp_map = {row[0]: row[1] for row in product_rows}
product_sp_map = {row[0]: row[2] for row in product_rows}
print(f"Inserted {len(products)} products.")

print("Generating stock...")
# Initial stock: random quantities between 20 and 200
stock_data = []
for pid in product_ids:
    qty = random.randint(20, 200)
    last_updated = START_DATE.isoformat()
    stock_data.append((pid, qty, last_updated))
cursor.executemany("INSERT INTO stock (product_id, quantity, last_updated) VALUES (?,?,?)", stock_data)
conn.commit()
print(f"Initial stock added for {len(stock_data)} products.")

# Track stock as we go
current_stock = {pid: qty for pid, qty, _ in stock_data}

print("Generating suppliers...")
suppliers = []
supplier_names = ["ABC Garments", "XYZ Textiles", "Fashion Hub", "Trendy Wear", "Classic Apparel", "Royal Fabrics", "Global Imports", "Local Craft"]
for name in supplier_names:
    contact = indian_name()
    phone = indian_phone()
    email = indian_email(contact)
    address = f"{random.randint(1, 100)} {random.choice(['MG Road', 'Park Street', 'Linking Road', 'Connaught Place'])}"
    city = random.choice(CITIES)
    suppliers.append((name, contact, phone, email, address, city))
cursor.executemany("INSERT INTO suppliers (name, contact_person, phone, email, address, city) VALUES (?,?,?,?,?,?)", suppliers)
conn.commit()
# Fetch supplier ids
cursor.execute("SELECT id FROM suppliers")
supplier_ids = [row[0] for row in cursor.fetchall()]
print(f"Inserted {len(suppliers)} suppliers.")

print("Generating purchases...")
# Simulate purchases over the period to replenish stock
purchase_data = []
purchase_items_data = []
purchase_invoice_set = set()

# We'll create 100-200 purchase orders
num_purchases = random.randint(100, 200)
for _ in range(num_purchases):
    supplier = random.choice(supplier_ids)
    purchase_date = random_date(START_DATE, END_DATE)
    # Unique invoice number
    while True:
        inv = f"INV-{random.randint(10000, 99999)}"
        if inv not in purchase_invoice_set:
            purchase_invoice_set.add(inv)
            break
    total = 0
    items = []
    # Each purchase contains 5-20 items
    num_items = random.randint(5, 20)
    for __ in range(num_items):
        pid = random.choice(product_ids)
        qty = random.randint(10, 100)
        # cost price may vary from current product cost (simulate fluctuation)
        base_cp = product_cp_map[pid]
        cost_price = round(base_cp * random.uniform(0.9, 1.1), 2)
        item_total = qty * cost_price
        total += item_total
        items.append((pid, qty, cost_price, item_total))
        # Update stock
        current_stock[pid] = current_stock.get(pid, 0) + qty
    transport = round(random.uniform(0, total * 0.05), 2)
    total += transport
    purchase_data.append((supplier, purchase_date.isoformat(), inv, total, transport, ""))
    # Insert purchase items later after purchase_id is known
    purchase_items_data.append(items)
# Insert purchases
cursor.executemany("INSERT INTO purchases (supplier_id, purchase_date, invoice_no, total_amount, transport_cost, notes) VALUES (?,?,?,?,?,?)", purchase_data)
conn.commit()
# Fetch purchase ids
cursor.execute("SELECT id FROM purchases")
purchase_ids = [row[0] for row in cursor.fetchall()]
# Insert purchase items
purchase_items_rows = []
for i, items in enumerate(purchase_items_data):
    purchase_id = purchase_ids[i]
    for (pid, qty, cp, tot) in items:
        purchase_items_rows.append((purchase_id, pid, qty, cp))
cursor.executemany("INSERT INTO purchase_items (purchase_id, product_id, quantity, cost_price) VALUES (?,?,?,?)", purchase_items_rows)
conn.commit()
print(f"Inserted {len(purchase_data)} purchases with {len(purchase_items_rows)} items.")

print("Generating sales...")
# Prepare sales data
sales_data = []
sale_items_data = []
# Get customer ids
cursor.execute("SELECT id FROM customers")
customer_ids = [row[0] for row in cursor.fetchall()]
# We'll generate sales in chronological order to properly handle stock and discounts
current = START_DATE
while current <= END_DATE:
    # Number of sales per day varies: weekends (Saturday/Sunday) have 1.5x more sales
    weekday = current.weekday()
    if weekday >= 5:  # Sat=5, Sun=6
        daily_sales = random.randint(80, 150)
    else:
        daily_sales = random.randint(40, 100)
    # Also increase around festival months (Oct-Dec)
    if current.month in [10, 11, 12]:
        daily_sales = int(daily_sales * 1.5)
    # Generate sales for the day
    for _ in range(daily_sales):
        if len(sales_data) >= NUM_SALES:
            break
        sale_date = current
        sale_time = random_time()
        customer = random.choice(customer_ids) if random.random() < 0.8 else None  # 80% registered customers
        worker = random.choice(worker_ids)
        # Payment type based on weights
        payment = random.choices(PAYMENT_TYPES, weights=PAYMENT_WEIGHTS)[0]
        # Number of items in sale: 1-5
        num_items = random.randint(1, 5)
        total_amount = 0
        discount_total = 0
        profit_total = 0
        items = []
        for __ in range(num_items):
            # Choose a product that has stock
            available = [pid for pid, qty in current_stock.items() if qty > 0]
            if not available:
                continue
            pid = random.choice(available)
            qty = random.randint(1, min(3, current_stock[pid]))
            if qty == 0:
                continue
            # Current selling price and cost price (use product's current values, but could have changed over time)
            sp = product_sp_map[pid]
            cp = product_cp_map[pid]
            # Discount between 0-20%
            discount = round(random.uniform(0, 20), 2)
            final_price_per_unit = sp * (1 - discount/100)
            item_total = qty * final_price_per_unit
            total_amount += item_total
            discount_total += qty * sp * (discount/100)
            profit_total += qty * (final_price_per_unit - cp)
            items.append((pid, qty, cp, sp, discount))
            # Reduce stock
            current_stock[pid] -= qty
        if items:
            sales_data.append((customer, worker, sale_date.isoformat(), sale_time, total_amount, payment, discount_total, profit_total))
            # Store items for later linking
            sale_items_data.append(items)
    if len(sales_data) >= NUM_SALES:
        break
    current += datetime.timedelta(days=1)

# Insert sales
cursor.executemany("INSERT INTO sales (customer_id, worker_id, sale_date, sale_time, total_amount, payment_type, discount_total, profit_total) VALUES (?,?,?,?,?,?,?,?)", sales_data)
conn.commit()
# Fetch sale ids
cursor.execute("SELECT id FROM sales")
sale_ids = [row[0] for row in cursor.fetchall()]
# Insert sale items
sale_items_rows = []
for i, items in enumerate(sale_items_data):
    sale_id = sale_ids[i]
    for (pid, qty, cp, sp, disc) in items:
        sale_items_rows.append((sale_id, pid, qty, cp, sp, disc))
cursor.executemany("INSERT INTO sale_items (sale_id, product_id, quantity, cost_price, selling_price, discount_percent) VALUES (?,?,?,?,?,?)", sale_items_rows)
conn.commit()
print(f"Inserted {len(sales_data)} sales with {len(sale_items_rows)} sale items.")

print("Updating customers.total_spent...")
# Update total spent per customer from sales
cursor.execute("""
    UPDATE customers
    SET total_spent = (
        SELECT COALESCE(SUM(total_amount), 0)
        FROM sales
        WHERE sales.customer_id = customers.id
    )
""")
conn.commit()

print("Updating stock after sales...")
# Update stock table with final quantities
for pid, qty in current_stock.items():
    cursor.execute("UPDATE stock SET quantity = ?, last_updated = ? WHERE product_id = ?", (qty, END_DATE.isoformat(), pid))
conn.commit()

print("Database generation complete!")
conn.close()