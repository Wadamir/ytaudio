import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("/storage/db/bot.sqlite3")


def get_conn():
	DB_PATH.parent.mkdir(parents=True, exist_ok=True)
	return sqlite3.connect(DB_PATH)


def init_db():
	with get_conn() as conn:
		conn.execute("""
			CREATE TABLE IF NOT EXISTS users (
				user_id INTEGER PRIMARY KEY,
				first_seen TEXT NOT NULL,
				last_seen TEXT NOT NULL
			)
		""")
		conn.commit()


def register_user(user_id: int):
	now = datetime.utcnow().isoformat()

	with get_conn() as conn:
		cur = conn.execute(
			"SELECT user_id FROM users WHERE user_id = ?",
			(user_id,)
		)

		if cur.fetchone() is None:
			conn.execute(
				"INSERT INTO users (user_id, first_seen, last_seen) VALUES (?, ?, ?)",
				(user_id, now, now)
			)
		else:
			conn.execute(
				"UPDATE users SET last_seen = ? WHERE user_id = ?",
				(now, user_id)
			)

		conn.commit()


def get_total_users() -> int:
	with get_conn() as conn:
		cur = conn.execute("SELECT COUNT(*) FROM users")
		return cur.fetchone()[0]
