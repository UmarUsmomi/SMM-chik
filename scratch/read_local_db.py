import sqlite3
import json

db_path = "d:/SMM/smm_database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== RECENT NEWS ITEMS ===")
cursor.execute("SELECT id, title, source, status, score, adapted_title, adapted_text FROM news_items ORDER BY id DESC LIMIT 5")
rows = cursor.fetchall()
for r in rows:
    print(f"ID: {r['id']}")
    print(f"Title: {r['title']}")
    print(f"Source: {r['source']}")
    print(f"Status: {r['status']}")
    print(f"Score: {r['score']}")
    print(f"Adapted Title: {r['adapted_title']}")
    print(f"Adapted Text: {r['adapted_text']}")
    print("-" * 50)

cursor.close()
conn.close()
