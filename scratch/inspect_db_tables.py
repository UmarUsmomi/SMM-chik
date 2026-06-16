import sqlite3

conn = sqlite3.connect("smm_database.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM app_settings;")
print("App Settings:")
for row in cursor.fetchall():
    print(row)

cursor.execute("SELECT id, title, score, status, url FROM news_items ORDER BY id DESC LIMIT 5;")
print("\nLatest 5 news items:")
for row in cursor.fetchall():
    print(row)

conn.close()
