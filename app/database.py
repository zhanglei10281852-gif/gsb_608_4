import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "township.db")

_conn = None


def get_connection():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS residents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            id_card TEXT NOT NULL UNIQUE,
            gender TEXT NOT NULL CHECK(gender IN ('男', '女')),
            birth_date TEXT NOT NULL,
            phone TEXT,
            address TEXT NOT NULL,
            village TEXT NOT NULL,
            household_head TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS affairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL CHECK(category IN ('户籍', '社保', '医保', '低保', '建房', '计生', '其他')),
            applicant_id INTEGER NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT '待受理' CHECK(status IN ('待受理', '办理中', '已办结', '已退回')),
            handler TEXT,
            result TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (applicant_id) REFERENCES residents(id)
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL CHECK(category IN ('通知', '公告', '政策', '公示')),
            publisher TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS affair_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            affair_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            handler TEXT,
            remark TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (affair_id) REFERENCES affairs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_affair_logs_affair_id
            ON affair_logs(affair_id);
    """)

    # 为既有事务补齐"创建"流转记录，避免历史数据时间线缺首条
    cursor.execute(
        """INSERT INTO affair_logs (affair_id, from_status, to_status, handler, remark, created_at)
           SELECT a.id, NULL, '待受理', NULL, '历史数据补录-创建', a.created_at
           FROM affairs a
           WHERE NOT EXISTS (
               SELECT 1 FROM affair_logs l WHERE l.affair_id = a.id
           )"""
    )

    conn.commit()
