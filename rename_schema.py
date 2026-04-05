import sqlite3
import random

DB_PATH = "retail.db"

# ---------- FETCH EXISTING DATA ----------

def get_existing_data(cursor):
    phones = set()
    emails = set()

    # Workers
    cursor.execute("SELECT phone, email FROM workers")
    for phone, email in cursor.fetchall():
        if phone:
            phones.add(phone)
        if email:
            emails.add(email)

    # Customers (if exists)
    try:
        cursor.execute("SELECT phone, email FROM customers")
        for phone, email in cursor.fetchall():
            if phone:
                phones.add(phone)
            if email:
                emails.add(email)
    except:
        pass

    return phones, emails


# ---------- GENERATORS ----------

def generate_unique_phone(existing_phones):
    while True:
        phone = str(random.randint(9000000000, 9999999999))
        if phone not in existing_phones:
            existing_phones.add(phone)
            return phone


def generate_unique_email(name, existing_emails):
    base = name.lower().replace(" ", ".")
    
    while True:
        num = random.randint(1, 9999)
        email = f"{base}{num}@company.com"
        if email not in existing_emails:
            existing_emails.add(email)
            return email


# ---------- MAIN UPDATE LOGIC ----------

def update_all_workers(cursor):
    print("Updating all workers with UNIQUE phone & email...\n")

    existing_phones, existing_emails = get_existing_data(cursor)

    # Using rowid (works even if no primary key exists)
    cursor.execute("SELECT rowid, name FROM workers")
    workers = cursor.fetchall()

    for rowid, name in workers:
        phone = generate_unique_phone(existing_phones)
        email = generate_unique_email(name, existing_emails)

        cursor.execute("""
            UPDATE workers
            SET phone = ?, email = ?
            WHERE rowid = ?
        """, (phone, email, rowid))


# ---------- DISPLAY SAMPLE ----------

def display_sample(cursor):
    print("\nSample Updated Workers:\n")
    cursor.execute("""
        SELECT name, phone, email 
        FROM workers 
        LIMIT 10
    """)
    rows = cursor.fetchall()

    for r in rows:
        print(f"Name: {r[0]}, Phone: {r[1]}, Email: {r[2]}")


# ---------- MAIN ----------

def main():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        update_all_workers(cursor)
        conn.commit()

        display_sample(cursor)

        conn.close()
        print("\n✅ All workers updated successfully with unique data.")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()