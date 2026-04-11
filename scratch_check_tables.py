import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('POSTGRESQL_DATABASE_URL_TELUGUWAP'))
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = [row[0] for row in cur.fetchall()]
print(f"Tables: {tables}")
if "app_parameters" not in tables:
    cur.execute("""
        CREATE TABLE app_parameters (
            id VARCHAR(24) PRIMARY KEY,
            parameter_code VARCHAR(100),
            parameter_data JSONB
        )
    """)
    print("Created app_parameters")
if "app_settings" not in tables:
    cur.execute("""
        CREATE TABLE app_settings (
            id VARCHAR(24) PRIMARY KEY,
            config_name VARCHAR(100),
            config_data JSONB
        )
    """)
    print("Created app_settings")
if "ads_config" not in tables:
    cur.execute("""
        CREATE TABLE ads_config (
            id VARCHAR(24) PRIMARY KEY,
            screen VARCHAR(100),
            ads_data JSONB
        )
    """)
    print("Created ads_config")
conn.commit()
print("Done.")
