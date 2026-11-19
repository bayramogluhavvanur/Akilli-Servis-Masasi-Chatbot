import os
from dotenv import load_dotenv
load_dotenv()

PG = dict(
    host=os.getenv("PG_HOST", "localhost"), port=os.getenv("PG_PORT", "5432"),
    dbname=os.getenv("PG_DB", "servis_masasi_db"),
    user=os.getenv("PG_USER", "postgres"), password=os.getenv("PG_PASSWORD", ""),
)
MSSQL_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;"
    "DATABASE=ServisMasasi_Auth;UID=sa;"
    f"PWD={{{os.getenv('MSSQL_PASSWORD', '')}}};TrustServerCertificate=yes;"
)
KB_TABLE = os.getenv("KB_TABLE", "knowledge_base_v2")
JWT_SECRET = os.getenv("JWT_SECRET", "")