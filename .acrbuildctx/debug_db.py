import sqlite3
import os

db_path = 'biometric_identity.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute('SELECT subject_id, biometric_type, commitment_hash, delta_storage_id FROM subjects')
rows = cur.fetchall()
for row in rows:
    print(row)
conn.close()
