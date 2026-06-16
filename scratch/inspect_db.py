import sqlite3
import pprint

conn = sqlite3.connect("smm_database.db")
cursor = conn.cursor()
cursor.execute("SELECT id, title, score, status, created_at FROM news_items ORDER BY id DESC LIMIT 20;")
rows = cursor.fetchall()
print("LATEST 20 NEWS ITEMS:")
for r in rows:
    print(r)

print("\nSTATS:")
cursor.execute("SELECT status, COUNT(*) FROM news_items GROUP BY status;")
print(cursor.fetchall())
conn.close()
