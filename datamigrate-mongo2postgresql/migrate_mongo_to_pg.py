import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json
from pymongo import MongoClient
from datetime import datetime

load_dotenv()
# 💡 Replace these with your actual connection strings
MONGO_URI = os.getenv("MONGO_URL")
MONGO_DB_NAME =  os.getenv("DB_NAME") # Database name inside Mongo

PG_URL = os.getenv("POSTGRESQL_DATABASE_URL_TELUGUWAP")

print(f'MONGO_URI: {MONGO_URI}')
print(f'MONGO_DB_NAME: {MONGO_DB_NAME}')
print(f'PG_URL: {PG_URL}')

def create_pg_tables(cur):
    print("Creating PostgreSQL tables...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS premium_users (
            id VARCHAR(24) PRIMARY KEY,
            plain_key VARCHAR(50),
            license_key VARCHAR(255),
            active_devices JSONB,
            created_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS devices (
            id VARCHAR(24) PRIMARY KEY,
            device_id VARCHAR(100),
            platform VARCHAR(50),
            registered_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cust_feedback_complaints (
            id VARCHAR(24) PRIMARY KEY,
            reference_no VARCHAR(50),
            name VARCHAR(100),
            subject VARCHAR(200),
            email VARCHAR(150),
            contact VARCHAR(50),
            description TEXT,
            created_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            id VARCHAR(24) PRIMARY KEY,
            config_name VARCHAR(100),
            config_data JSONB
        );

        CREATE TABLE IF NOT EXISTS app_parameters (
            id VARCHAR(24) PRIMARY KEY,
            parameter_code VARCHAR(100),
            parameter_data JSONB
        );

        CREATE TABLE IF NOT EXISTS ads_config (
            id VARCHAR(24) PRIMARY KEY,
            screen VARCHAR(50),
            ads_data JSONB
        );

        CREATE TABLE IF NOT EXISTS radio_stations (
            id VARCHAR(24) PRIMARY KEY,
            station_id VARCHAR(50),
            name VARCHAR(200),
            logo_url TEXT,
            stream_url TEXT,
            language VARCHAR(100),
            genre VARCHAR(100),
            page VARCHAR(200)
        );

        CREATE TABLE IF NOT EXISTS radio_garden_channels (
            id VARCHAR(24) PRIMARY KEY,
            radio_garden_id VARCHAR(50),
            country VARCHAR(100),
            genre VARCHAR(100),
            channel_id VARCHAR(50),
            language VARCHAR(100),
            logo_url TEXT,
            name VARCHAR(200),
            page VARCHAR(255),
            state VARCHAR(100),
            stream_url TEXT
        );
    """)


def migrate_database():
    # 1. Connect to both databases
    print("Connecting to databases...")
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB_NAME]

    pg_conn = psycopg2.connect(PG_URL)
    pg_cur = pg_conn.cursor()

    # 2. Create tables
    create_pg_tables(pg_cur)
    pg_conn.commit()

    # --- MIGRATION LOGIC ---

    # 1. Premium Users
    print("Migrating premium_users...")
    for doc in mongo_db['premium_users'].find():
        pg_cur.execute("""
            INSERT INTO premium_users (id, plain_key, license_key, active_devices, created_at)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
        """, (
            str(doc['_id']), doc.get('plain_key'), doc.get('license_key'),
            Json(doc.get('active_devices', [])), doc.get('created_at')
        ))

    # 2. Devices
    print("Migrating devices...")
    for doc in mongo_db['devices'].find():
        pg_cur.execute("""
            INSERT INTO devices (id, device_id, platform, registered_at)
            VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
        """, (
            str(doc['_id']), doc.get('deviceId'), doc.get('platform'), doc.get('registeredAt')
        ))

    # 3. Complaints
    print("Migrating cust_feedback_complaints...")
    for doc in mongo_db['cust_feedback_complaints'].find():
        pg_cur.execute("""
            INSERT INTO cust_feedback_complaints (id, reference_no, name, subject, email, contact, description, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
        """, (
            str(doc['_id']), doc.get('reference_no'), doc.get('name'), doc.get('subject'),
            doc.get('email'), doc.get('contact'), doc.get('description'), doc.get('created_at')
        ))

    # 4. App Settings
    print("Migrating app_settings...")
    for doc in mongo_db['app_settings'].find():
        m_id = str(doc.pop('_id'))
        config_name = doc.pop('config_name', 'unknown')
        pg_cur.execute("""
            INSERT INTO app_settings (id, config_name, config_data) 
            VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING;
        """, (m_id, config_name, Json(doc)))

    # 5. App Parameters
    print("Migrating app_parameters...")
    for doc in mongo_db['app_parameters'].find():
        m_id = str(doc.pop('_id'))
        p_code = doc.pop('parameter_code', doc.pop('config_key', 'unknown'))
        # Standardize datetime strings to isoformat if they exist inside the flexible JSON
        if 'created_at' in doc and isinstance(doc['created_at'], datetime):
            doc['created_at'] = doc['created_at'].isoformat()

        pg_cur.execute("""
            INSERT INTO app_parameters (id, parameter_code, parameter_data) 
            VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING;
        """, (m_id, p_code, Json(doc)))

    # 6. Ads Config
    print("Migrating ads_config...")
    for doc in mongo_db['ads_config'].find():
        m_id = str(doc.pop('_id'))
        screen = doc.pop('screen', 'global')
        pg_cur.execute("""
            INSERT INTO ads_config (id, screen, ads_data) 
            VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING;
        """, (m_id, screen, Json(doc)))

    # 7. Radio Stations
    print("Migrating radio_stations...")
    for doc in mongo_db['radio_stations'].find():
        pg_cur.execute("""
            INSERT INTO radio_stations (id, station_id, name, logo_url, stream_url, language, genre, page)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
        """, (
            str(doc['_id']), doc.get('id'), doc.get('name'), doc.get('logoUrl'),
            doc.get('streamUrl'), doc.get('language'), doc.get('genre'), doc.get('page')
        ))

    # 8. Radio Garden Channels
    print("Migrating radio_garden_channels...")
    for doc in mongo_db['radio_garden_channels'].find():
        pg_cur.execute("""
            INSERT INTO radio_garden_channels (id, radio_garden_id, country, genre, channel_id, language, logo_url, name, page, state, stream_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
        """, (
            str(doc['_id']), doc.get('radio_garden_id'), doc.get('country'), doc.get('genre'),
            doc.get('id'), doc.get('language'), doc.get('logoUrl'), doc.get('name'),
            doc.get('page'), doc.get('state'), doc.get('streamUrl')
        ))

    # Commit all inserts and close connections
    pg_conn.commit()
    pg_cur.close()
    pg_conn.close()
    mongo_client.close()
    print("✅ Direct Database Migration completed successfully!")


if __name__ == "__main__":
    migrate_database()