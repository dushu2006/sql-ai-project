import sqlite3
import json

def get_deep_schema(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    
    deep_schema = {}
    for table in tables:
        table_name = table['name']
        original_sql = table['sql']
        
        # Get sample data
        cur.execute(f"SELECT * FROM {table_name} LIMIT 3;")
        sample_rows = [dict(row) for row in cur.fetchall()]
        
        deep_schema[table_name] = {
            "sql": original_sql,
            "sample": sample_rows
        }
    
    conn.close()
    return deep_schema

if __name__ == "__main__":
    db_path = 'retail.db'
    schema_info = get_deep_schema(db_path)
    print(json.dumps(schema_info, indent=2))
