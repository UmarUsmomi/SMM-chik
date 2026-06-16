import sqlite3
import pprint

conn = sqlite3.connect("smm_database.db")
cursor = conn.cursor()

cursor.execute("SELECT id, title, adapted_title, adapted_text, status, created_at FROM news_items WHERE title LIKE '%rsync%' OR adapted_title LIKE '%rsync%';")
rows = cursor.fetchall()

print("MATCHING ITEMS:")
for r in rows:
    print("ID:", r[0])
    print("Title:", r[1])
    print("Adapted Title:", r[2])
    print("Adapted Text:\n", r[3])
    print("Status:", r[4])
    print("Created At:", r[5])
    print("-" * 50)

conn.close()
