import sqlite3
import os

DB_PATH = os.path.join(r"C:\Users\HP\OneDrive\Documents\sql-ai-project", "retail.db")

def print_schema():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' OR type='trigger' OR type='index'")
    for row in cur.fetchall():
        if row[0]:
            print(row[0] + ";\n")

if __name__ == "__main__":
    print_schema()
