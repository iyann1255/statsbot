import sqlite3, os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statbot.db")

def get_con():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = get_con()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id    INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            username   TEXT,
            full_name  TEXT,
            date       TEXT NOT NULL,  -- YYYY-MM-DD
            hour       INTEGER NOT NULL,
            count      INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS daily_stats (
            chat_id  INTEGER NOT NULL,
            user_id  INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            date     TEXT NOT NULL,
            count    INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id, date)
        );
    """)
    con.commit(); con.close()

def record_message(chat_id: int, user_id: int, username: str, full_name: str, date: str, hour: int):
    con = get_con()
    con.execute("""
        INSERT INTO daily_stats (chat_id, user_id, username, full_name, date, count)
        VALUES (?,?,?,?,?,1)
        ON CONFLICT(chat_id, user_id, date) DO UPDATE SET
            count = count + 1,
            username = excluded.username,
            full_name = excluded.full_name
    """, (chat_id, user_id, username, full_name, date))
    con.execute("""
        INSERT INTO messages (chat_id, user_id, username, full_name, date, hour)
        VALUES (?,?,?,?,?,?)
    """, (chat_id, user_id, username, full_name, date, hour))
    con.commit(); con.close()

def get_top_members(chat_id: int, limit: int = 10, days: int = 30):
    con = get_con()
    rows = con.execute("""
        SELECT user_id, username, full_name, SUM(count) as total
        FROM daily_stats
        WHERE chat_id=? AND date >= date('now', ?)
        GROUP BY user_id ORDER BY total DESC LIMIT ?
    """, (chat_id, f'-{days} days', limit)).fetchall()
    con.close()
    return rows

def get_daily_totals(chat_id: int, days: int = 7):
    con = get_con()
    rows = con.execute("""
        SELECT date, SUM(count) as total
        FROM daily_stats
        WHERE chat_id=? AND date >= date('now', ?)
        GROUP BY date ORDER BY date ASC
    """, (chat_id, f'-{days} days')).fetchall()
    con.close()
    return rows

def get_hourly_stats(chat_id: int, days: int = 7):
    con = get_con()
    rows = con.execute("""
        SELECT hour, COUNT(*) as total
        FROM messages
        WHERE chat_id=? AND date >= date('now', ?)
        GROUP BY hour ORDER BY hour ASC
    """, (chat_id, f'-{days} days')).fetchall()
    con.close()
    return rows

def get_user_stats(chat_id: int, user_id: int):
    con = get_con()
    row = con.execute("""
        SELECT full_name, username,
               SUM(count) as total,
               SUM(CASE WHEN date >= date('now', '-7 days') THEN count ELSE 0 END) as week,
               SUM(CASE WHEN date >= date('now', '-1 days') THEN count ELSE 0 END) as today
        FROM daily_stats
        WHERE chat_id=? AND user_id=?
    """, (chat_id, user_id)).fetchone()
    rank = con.execute("""
        SELECT COUNT(*)+1 FROM (
            SELECT user_id, SUM(count) as total
            FROM daily_stats WHERE chat_id=?
            GROUP BY user_id
            HAVING total > (
                SELECT COALESCE(SUM(count),0) FROM daily_stats WHERE chat_id=? AND user_id=?
            )
        )
    """, (chat_id, chat_id, user_id)).fetchone()[0]
    con.close()
    return row, rank

def get_chat_total(chat_id: int):
    con = get_con()
    row = con.execute("SELECT SUM(count) FROM daily_stats WHERE chat_id=?", (chat_id,)).fetchone()
    con.close()
    return row[0] or 0

def get_users_monthly_total(chat_id: int, year: int, month: int, user_ids: list):
    if not user_ids:
        return {}
    con = get_con()
    placeholders = ",".join("?" * len(user_ids))
    rows = con.execute(f"""
        SELECT user_id, SUM(count) as total
        FROM daily_stats
        WHERE chat_id=? AND strftime('%Y-%m', date)=? AND user_id IN ({placeholders})
        GROUP BY user_id
    """, (chat_id, f"{year:04d}-{month:02d}", *user_ids)).fetchall()
    con.close()
    return {r["user_id"]: r["total"] for r in rows}

def get_unique_users(chat_id: int):
    con = get_con()
    row = con.execute("SELECT COUNT(DISTINCT user_id) FROM daily_stats WHERE chat_id=?", (chat_id,)).fetchone()
    con.close()
    return row[0] or 0

def get_monthly_stats(chat_id: int, year: int, month: int):
    con = get_con()
    rows = con.execute("""
        SELECT user_id, username, full_name, date, SUM(count) as total
        FROM daily_stats
        WHERE chat_id=? AND strftime('%Y-%m', date)=?
        GROUP BY user_id, date ORDER BY date ASC, total DESC
    """, (chat_id, f"{year:04d}-{month:02d}")).fetchall()
    con.close()
    return rows
