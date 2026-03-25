import psycopg2
import os
import sys

# Assume run from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
POSTGRESQL_DATABASE_URL_TELUGUWAP = os.environ.get("POSTGRESQL_DATABASE_URL_TELUGUWAP")


def setup_db():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    cur = conn.cursor()

    commands = [
        """
        CREATE TABLE IF NOT EXISTS hindiflacs_collection_type_header (
            id SERIAL PRIMARY KEY,
            header_name VARCHAR(255) UNIQUE NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hindiflacs_collection_type_details (
            id SERIAL PRIMARY KEY,
            header_id INTEGER REFERENCES hindiflacs_collection_type_header(id) ON DELETE CASCADE,
            option_value VARCHAR(255) UNIQUE NOT NULL,
            option_text VARCHAR(255) NOT NULL,
            count INTEGER DEFAULT 0,
            language VARCHAR(50),
            details_status VARCHAR(50) DEFAULT 'unprocessed',
            details_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hindiflacs_albums_list (
            id SERIAL PRIMARY KEY,
            album_name VARCHAR(255) NOT NULL,
            album_link VARCHAR(255) UNIQUE NOT NULL,
            album_cover TEXT,
            hindiflacs_actors TEXT,
            director_name VARCHAR(255),
            music_director VARCHAR(255),
            total_files INTEGER DEFAULT 0,
            album_type VARCHAR(100),
            year INTEGER,
            rating VARCHAR(50),
            collection_id INTEGER REFERENCES hindiflacs_collection_type_details(id) ON DELETE SET NULL,
            details_status VARCHAR(50) DEFAULT 'pending',
            details_last_error TEXT,
            details_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hindiflacs_actors (
            id SERIAL PRIMARY KEY,
            actor_name VARCHAR(255) NOT NULL,
            actor_link VARCHAR(255),
            album_id INTEGER REFERENCES hindiflacs_albums_list(id) ON DELETE CASCADE,
            UNIQUE(actor_link, album_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hindiflacs_directors (
            id SERIAL PRIMARY KEY,
            director_name VARCHAR(255) NOT NULL,
            director_link VARCHAR(255),
            album_id INTEGER REFERENCES hindiflacs_albums_list(id) ON DELETE CASCADE,
            UNIQUE(director_link, album_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hindiflacs_music_directors (
            id SERIAL PRIMARY KEY,
            music_director_name VARCHAR(255) NOT NULL,
            music_director_link VARCHAR(255),
            album_id INTEGER REFERENCES hindiflacs_albums_list(id) ON DELETE CASCADE,
            UNIQUE(music_director_link, album_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hindiflacs_singers (
            id SERIAL PRIMARY KEY,
            singer_name VARCHAR(255) UNIQUE NOT NULL,
            singer_link VARCHAR(255)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hindiflacs_songs (
            id SERIAL PRIMARY KEY,
            album_id INTEGER REFERENCES hindiflacs_albums_list(id) ON DELETE CASCADE,
            song_name VARCHAR(255) NOT NULL,
            song_link VARCHAR(255) UNIQUE NOT NULL,
            play_link VARCHAR(255),
            duration VARCHAR(50),
            hindiflacs_singers TEXT,
            composer VARCHAR(255),
            download_link_original TEXT,
            download_text_original VARCHAR(255),
            download_size_original VARCHAR(100),
            download_link_128kbps TEXT,
            download_text_128kbps VARCHAR(255),
            download_size_128kbps VARCHAR(100),
            download_link_320kbps TEXT,
            download_text_320kbps VARCHAR(255),
            download_size_320kbps VARCHAR(100),
            details_status VARCHAR(50) DEFAULT 'pending',
            details_last_error TEXT,
            details_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            blomp_user_id INTEGER,
            blomp_path_original TEXT,
            blomp_hash_original VARCHAR(255),
            blomp_path_128kbps TEXT,
            blomp_hash_128kbps VARCHAR(255),
            blomp_path_320kbps TEXT,
            blomp_hash_320kbps VARCHAR(255)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hindiflacs_song_singers (
            song_id INTEGER REFERENCES hindiflacs_songs(id) ON DELETE CASCADE,
            singer_id INTEGER REFERENCES hindiflacs_singers(id) ON DELETE CASCADE,
            PRIMARY KEY (song_id, singer_id)
        )
        """
    ]

    for command in commands:
        cur.execute(command)

    conn.commit()
    cur.close()
    conn.close()
    print("Database tables created successfully for hindiflacs.")

if __name__ == '__main__':
    setup_db()
