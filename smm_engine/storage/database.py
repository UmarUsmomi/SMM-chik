import os
import json
import sqlite3
import contextvars
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from smm_engine.config import SQLITE_DB_PATH, DATABASE_URL

logger = logging.getLogger(__name__)

# Context-local connection storage to reuse connection within the same task/request
# and avoid concurrent database access conflicts or connection exhaustion.
_conn_var = contextvars.ContextVar("db_connection", default=None)

class ConnectionProxy:
    """Wrapper that prevents closing the connection prematurely in helper methods"""
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        # Prevent closing to keep connection cached/alive in context
        pass

    def real_close(self):
        # Actually close the connection
        self._conn.close()

class DatabaseManager:
    def __init__(self):
        self.use_postgres = bool(DATABASE_URL)
        _conn_var.set(None)
        self._init_db()

    def close_current(self):
        """Manually closes the context-cached connection if any"""
        conn = _conn_var.get()
        if conn:
            try:
                conn.real_close()
            except Exception:
                pass
            _conn_var.set(None)

    def _get_connection(self):
        conn = _conn_var.get()
        
        # 1. Check if cached connection exists and is alive
        if conn:
            try:
                if self.use_postgres:
                    with conn._conn.cursor() as cur:
                        cur.execute("SELECT 1")
                else:
                    conn._conn.execute("SELECT 1")
                return conn
            except Exception:
                # Connection is dead, release it
                try:
                    conn.real_close()
                except Exception:
                    pass
                _conn_var.set(None)

        # 2. Establish a new connection and cache it as a proxy
        if self.use_postgres:
            import psycopg2
            try:
                new_conn = psycopg2.connect(DATABASE_URL)
                new_conn.autocommit = True  # Enable autocommit to prevent transactions from hanging open
                proxy = ConnectionProxy(new_conn)
                _conn_var.set(proxy)
                return proxy
            except Exception as e:
                logger.error("\n" + "="*80 + "\n" +
                             f"❌ DATABASE CONNECTION ERROR:\n"
                             f"Failed to connect to the PostgreSQL database using DATABASE_URL.\n"
                             f"Error details: {e}\n"
                             f"Make sure you are using the Supabase Connection Pooler (port 6543) instead of direct connection (port 5432).\n"
                             f"Direct connections (5432) do not support IPv4 on Render's free tier.\n" +
                             "="*80 + "\n")
                raise RuntimeError(
                    f"❌ DATABASE CONNECTION ERROR: Failed to connect to the database. "
                    f"Ensure DATABASE_URL is correct and uses port 6543. Original error: {e}"
                ) from e
        else:
            new_conn = sqlite3.connect(SQLITE_DB_PATH)
            new_conn.isolation_level = None  # Enable autocommit for SQLite
            proxy = ConnectionProxy(new_conn)
            _conn_var.set(proxy)
            return proxy

    def _init_db(self):
        """Initializes tables if they do not exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # SQL for tables (supports syntax dialect for both sqlite and postgres)
        if self.use_postgres:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS news_items (
                id SERIAL PRIMARY KEY,
                source VARCHAR(50) NOT NULL,
                source_id VARCHAR(100) NOT NULL,
                title TEXT NOT NULL,
                url TEXT,
                raw_data TEXT,
                score INTEGER DEFAULT 0,
                score_reason TEXT,
                status VARCHAR(30) DEFAULT 'parsed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                adapted_title TEXT,
                adapted_text TEXT,
                media_url TEXT,
                media_type VARCHAR(50),
                UNIQUE(source, source_id)
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        else:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT,
                raw_data TEXT,
                score INTEGER DEFAULT 0,
                score_reason TEXT,
                status TEXT DEFAULT 'parsed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                adapted_title TEXT,
                adapted_text TEXT,
                media_url TEXT,
                media_type TEXT,
                UNIQUE(source, source_id)
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        
        # Execute each statement separately for compatibility (especially with multiple statements in sqlite)
        for statement in create_table_sql.strip().split(";"):
            if statement.strip():
                cursor.execute(statement)
        conn.commit()
        cursor.close()
        conn.close()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves an application setting"""
        conn = self._get_connection()
        cursor = conn.cursor()
        param_placeholder = "%s" if self.use_postgres else "?"
        cursor.execute(f"SELECT value FROM app_settings WHERE key = {param_placeholder}", (key,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row[0] if row else default

    def set_setting(self, key: str, value: Any):
        """Sets an application setting"""
        conn = self._get_connection()
        cursor = conn.cursor()
        param_placeholder = "%s" if self.use_postgres else "?"
        
        if self.use_postgres:
            query = """
                INSERT INTO app_settings (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
            """
            cursor.execute(query, (key, str(value)))
        else:
            query = """
                INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?);
            """
            cursor.execute(query, (key, str(value)))
            
        conn.commit()
        cursor.close()
        conn.close()

    def is_duplicate(self, source: str, source_id: str, url: str = None) -> bool:
        """Checks if a story has already been parsed before"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        placeholder = "%s" if self.use_postgres else "?"
        
        # Check by source & source_id
        cursor.execute(f"SELECT id FROM news_items WHERE source = {placeholder} AND source_id = {placeholder}", (source, source_id))
        row = cursor.fetchone()
        
        if row:
            cursor.close()
            conn.close()
            return True
            
        # Also check by URL if provided
        if url:
            cursor.execute(f"SELECT id FROM news_items WHERE url = {placeholder}", (url,))
            row = cursor.fetchone()
            if row:
                cursor.close()
                conn.close()
                return True
                
        cursor.close()
        conn.close()
        return False

    def save_news_item(self, source: str, source_id: str, title: str, url: str, raw_data: Dict[str, Any]) -> int:
        """Saves a parsed news item to the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        raw_json = json.dumps(raw_data, ensure_ascii=False)
        now = datetime.now()
        
        try:
            if self.use_postgres:
                cursor.execute(
                    """
                    INSERT INTO news_items (source, source_id, title, url, raw_data, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source, source_id) DO NOTHING
                    RETURNING id;
                    """,
                    (source, source_id, title, url, raw_json, now)
                )
                res = cursor.fetchone()
                item_id = res[0] if res else None
            else:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO news_items (source, source_id, title, url, raw_data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (source, source_id, title, url, raw_json, now)
                )
                item_id = cursor.lastrowid
                
            conn.commit()
            return item_id
        except Exception as e:
            logger.error(f"Error saving news item: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def update_scoring(self, item_id: int, score: int, reason: str, status: str = 'parsed'):
        """Updates scoring info for a specific news item"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        param_placeholder = "%s" if self.use_postgres else "?"
        query = f"""
            UPDATE news_items 
            SET score = {param_placeholder}, score_reason = {param_placeholder}, status = {param_placeholder}
            WHERE id = {param_placeholder}
        """
        
        cursor.execute(query, (score, reason, status, item_id))
        conn.commit()
        cursor.close()
        conn.close()

    def save_adapted_content(self, item_id: int, title: str, text: str, status: str = 'pending_review'):
        """Saves generated adapted content"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        param_placeholder = "%s" if self.use_postgres else "?"
        query = f"""
            UPDATE news_items 
            SET adapted_title = {param_placeholder}, adapted_text = {param_placeholder}, status = {param_placeholder}
            WHERE id = {param_placeholder}
        """
        
        cursor.execute(query, (title, text, status, item_id))
        conn.commit()
        cursor.close()
        conn.close()

    def save_media_info(self, item_id: int, media_url: str, media_type: str):
        """Saves generated media information"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        param_placeholder = "%s" if self.use_postgres else "?"
        query = f"""
            UPDATE news_items 
            SET media_url = {param_placeholder}, media_type = {param_placeholder}
            WHERE id = {param_placeholder}
        """
        
        cursor.execute(query, (media_url, media_type, item_id))
        conn.commit()
        cursor.close()
        conn.close()

    def mark_published(self, item_id: int):
        """Marks a story as published"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        param_placeholder = "%s" if self.use_postgres else "?"
        now = datetime.now()
        query = f"""
            UPDATE news_items 
            SET status = 'published', published_at = {param_placeholder}
            WHERE id = {param_placeholder}
        """
        
        cursor.execute(query, (now, item_id))
        conn.commit()
        cursor.close()
        conn.close()

    def get_queue(self, status: str = 'pending_review', limit: int = 10) -> List[Dict[str, Any]]:
        """Gets items in queue with specific status"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        param_placeholder = "%s" if self.use_postgres else "?"
        cursor.execute(
            f"SELECT id, source, source_id, title, url, score, score_reason, status, adapted_title, adapted_text, media_url, media_type, created_at "
            f"FROM news_items WHERE status = {param_placeholder} ORDER BY score DESC, created_at DESC LIMIT {limit}",
            (status,)
        )
        
        columns = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
            
        cursor.close()
        conn.close()
        return results

    def get_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a news item by its ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        param_placeholder = "%s" if self.use_postgres else "?"
        cursor.execute(
            f"SELECT id, source, source_id, title, url, score, score_reason, status, adapted_title, adapted_text, media_url, media_type, created_at "
            f"FROM news_items WHERE id = {param_placeholder}",
            (item_id,)
        )
        
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if row:
            return dict(zip(columns, row))
        return None

    def get_recent_items(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves recent titles and URLs for fuzzy deduplication"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        param_placeholder = "%s" if self.use_postgres else "?"
        cursor.execute(
            f"SELECT id, title, url FROM news_items ORDER BY created_at DESC LIMIT {param_placeholder}",
            (limit,)
        )
        
        columns = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
            
        cursor.close()
        conn.close()
        return results

    def get_publication_stats(self) -> List[Dict[str, Any]]:
        """Retrieves publication counts grouped by day for the last 7 days"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # SQLite uses date(published_at), PostgreSQL date(published_at) or CAST(published_at AS DATE)
        # DATE(published_at) is compatible with both.
        query = """
            SELECT DATE(published_at) as pub_date, COUNT(id) as pub_count 
            FROM news_items 
            WHERE status = 'published' AND published_at IS NOT NULL 
            GROUP BY pub_date 
            ORDER BY pub_date ASC 
            LIMIT 7
        """
        
        cursor.execute(query)
        results = []
        for row in cursor.fetchall():
            results.append({
                "date": row[0],
                "count": row[1]
            })
            
        cursor.close()
        conn.close()
        return results

    def get_stats(self) -> dict:
        """Gets count of news items by status"""
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholder = "%s" if self.use_postgres else "?"
        stats = {}
        for status in ['parsed', 'pending_review', 'published', 'rejected']:
            cursor.execute(f"SELECT COUNT(id) FROM news_items WHERE status = {placeholder}", (status,))
            stats[status] = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return stats
