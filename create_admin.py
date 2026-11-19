import os
from dotenv import load_dotenv
import db_mssql

load_dotenv()

username = os.getenv("ADMIN_USERNAME", "admin")
email = os.getenv("ADMIN_EMAIL")
password = os.getenv("ADMIN_PASSWORD")
full_name = os.getenv("ADMIN_FULL_NAME", "Sistem Yöneticisi")

if not email or not password:
    raise SystemExit(".env içinde ADMIN_EMAIL ve ADMIN_PASSWORD tanımlayın.")

ok, msg = db_mssql.register_user(
    username=username,
    email=email,
    password=password,
    full_name=full_name,
    role="admin",
)
print(("[+] " if ok else "[!] ") + str(msg))