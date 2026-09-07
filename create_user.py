import bcrypt
from db import get_connection

username = "admin"
password = "admin123"   # change later
full_name = "System Admin"
role_id = 1             # Admin role

# hash password
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

conn = get_connection()
cur = conn.cursor()

cur.execute("""
    INSERT INTO users (username, password_hash, full_name, role_id)
    VALUES (%s, %s, %s, %s)
""", (username, hashed, full_name, role_id))

conn.commit()
cur.close()
conn.close()

print("✅ Admin user created successfully")
