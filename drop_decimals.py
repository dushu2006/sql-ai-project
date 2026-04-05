import sqlite3
import os

DB_PATH = os.path.join(r"C:\Users\HP\OneDrive\Documents\sql-ai-project", "retail.db")

def drop_decimals():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cur.fetchall()]
        
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            columns = [c[1] for c in cur.fetchall()]
            
            for col in columns:
                if any(keyword in col.lower() for keyword in ['amount', 'price', 'discount', 'spent', 'profit', 'cost']):
                    print(f"Rounding decimals internally for {table}.{col}")
                    cur.execute(f"UPDATE {table} SET {col} = CAST(ROUND({col}) AS INTEGER) WHERE {col} IS NOT NULL")
                    
        conn.commit()
        conn.close()
        print("Database fields updated to clean integers!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    drop_decimals()
