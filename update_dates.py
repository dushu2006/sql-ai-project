import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(r"C:\Users\HP\OneDrive\Documents\sql-ai-project", "retail.db")

def update_dates():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Get all tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cur.fetchall()]
        
        # We need a reference offset to move everything up to today. 
        # Usually sales date_time is a good anchor.
        cur.execute("SELECT MAX(date_time) FROM sales")
        max_date_str = cur.fetchone()[0]
        
        if not max_date_str:
            print("No dates found in sales table.")
            return

        max_date = datetime.strptime(max_date_str.split()[0], '%Y-%m-%d')
        today = datetime.now()
        diff_days = (today - max_date).days
        
        if diff_days == 0:
            print("Database is already up to date!")
            return
            
        print(f"Offsetting all database dates forward by {diff_days} days to align with {today.strftime('%Y-%m-%d')}...")

        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            columns = [c[1] for c in cur.fetchall()]
            for col in columns:
                lower_col = col.lower()
                if 'date' in lower_col or 'time' in lower_col or lower_col == 'timestamp':
                    try:
                        cur.execute(f"UPDATE {table} SET {col} = datetime({col}, '+{diff_days} days') WHERE {col} IS NOT NULL")
                        print(f" -> Updated {table}.{col}")
                    except sqlite3.OperationalError as e:
                        print(f" -> Skipped {table}.{col} (could not parse as datetime: {e})")

        # Also replenish out-of-stock items slightly so there's always something to show
        try:
            cur.execute("UPDATE stock SET quantity = quantity + 50 WHERE quantity < 10")
            print(" -> Restocked low-quantity items.")
        except:
            pass
            
        conn.commit()
        conn.close()
        print("Successfully updated database to current date!")
    
    except Exception as e:
        print(f"Error updating database: {e}")

if __name__ == "__main__":
    update_dates()
