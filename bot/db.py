import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path("/storage/db/bot.sqlite3")


# --------------------------------------------------
# Connection
# --------------------------------------------------
def get_conn():
	DB_PATH.parent.mkdir(parents=True, exist_ok=True)
	return sqlite3.connect(DB_PATH)


# --------------------------------------------------
# Init DB
# --------------------------------------------------
def init_db():
	with get_conn() as conn:
		# --- users ---
		conn.execute("""
			CREATE TABLE IF NOT EXISTS users (
				user_id INTEGER PRIMARY KEY,

				username TEXT,
				first_name TEXT,
				last_name TEXT,

				first_seen TEXT NOT NULL,
				last_seen TEXT NOT NULL,

				downloads_count INTEGER DEFAULT 0,
				last_video_at TEXT
			)
		""")

		# --- downloads ---
		conn.execute("""
			CREATE TABLE IF NOT EXISTS downloads (
				id INTEGER PRIMARY KEY AUTOINCREMENT,

				user_id INTEGER NOT NULL,

				video_url TEXT NOT NULL,
				video_id TEXT,
				video_title TEXT,

				duration_seconds INTEGER,

				chosen_bitrate INTEGER,
				estimated_size_mb REAL,
				real_size_mb REAL,

				delivery_method TEXT NOT NULL,
				-- telegram | link | failed

				file_path TEXT,
				download_url TEXT,

				fallback_reason TEXT,
				-- too_large | long_video | timeout | NULL

				status TEXT NOT NULL,
				-- success | failed

				error_message TEXT,

				created_at TEXT NOT NULL,

				FOREIGN KEY (user_id) REFERENCES users(user_id)
			)
		""")
		
		# --- youtube_errors ---
		conn.execute("""
			CREATE TABLE IF NOT EXISTS youtube_errors (
				id INTEGER PRIMARY KEY AUTOINCREMENT,

				error_type TEXT NOT NULL,
				video_url TEXT,
				video_id TEXT,

				created_at TEXT NOT NULL
			)
		""")

		conn.commit()


# --------------------------------------------------
# Users
# --------------------------------------------------
def register_user(user) -> None:
	now = datetime.utcnow().isoformat()

	with get_conn() as conn:
		cur = conn.execute(
			"SELECT user_id FROM users WHERE user_id = ?",
			(user.id,)
		)

		if cur.fetchone() is None:
			conn.execute("""
				INSERT INTO users (
					user_id,
					username,
					first_name,
					last_name,
					first_seen,
					last_seen,
					downloads_count
				)
				VALUES (?, ?, ?, ?, ?, ?, 0)
			""", (
				user.id,
				user.username,
				user.first_name,
				user.last_name,
				now,
				now,
			))
		else:
			conn.execute("""
				UPDATE users
				SET
					username = ?,
					first_name = ?,
					last_name = ?,
					last_seen = ?
				WHERE user_id = ?
			""", (
				user.username,
				user.first_name,
				user.last_name,
				now,
				user.id,
			))

		conn.commit()


def get_total_users() -> int:
	with get_conn() as conn:
		cur = conn.execute("SELECT COUNT(*) FROM users")
		return cur.fetchone()[0]


# --------------------------------------------------
# Downloads
# --------------------------------------------------
def increment_downloads(user_id: int) -> None:
	now = datetime.utcnow().isoformat()

	with get_conn() as conn:
		conn.execute("""
			UPDATE users
			SET
				downloads_count = downloads_count + 1,
				last_video_at = ?
			WHERE user_id = ?
		""", (now, user_id))
		conn.commit()


def log_download(
	user_id: int,
	video_url: str,
	video_id: Optional[str],
	video_title: Optional[str],
	duration_seconds: Optional[int],

	chosen_bitrate: Optional[int],
	estimated_size_mb: Optional[float],
	real_size_mb: Optional[float],

	delivery_method: str,
	status: str,

	file_path: Optional[str] = None,
	download_url: Optional[str] = None,
	fallback_reason: Optional[str] = None,
	error_message: Optional[str] = None,
) -> None:
	with get_conn() as conn:
		conn.execute("""
			INSERT INTO downloads (
				user_id,
				video_url,
				video_id,
				video_title,
				duration_seconds,
				chosen_bitrate,
				estimated_size_mb,
				real_size_mb,
				delivery_method,
				file_path,
				download_url,
				fallback_reason,
				status,
				error_message,
				created_at
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		""", (
			user_id,
			video_url,
			video_id,
			video_title,
			duration_seconds,
			chosen_bitrate,
			estimated_size_mb,
			real_size_mb,
			delivery_method,
			file_path,
			download_url,
			fallback_reason,
			status,
			error_message,
			datetime.utcnow().isoformat(),
		))
		conn.commit()


# --------------------------------------------------
# Errors
# --------------------------------------------------
def log_youtube_error(
	error_type: str,
	video_url: Optional[str] = None,
	video_id: Optional[str] = None,
) -> None:
	with get_conn() as conn:
		conn.execute("""
			INSERT INTO youtube_errors (
				error_type,
				video_url,
				video_id,
				created_at
			)
			VALUES (?, ?, ?, ?)
		""", (
			error_type,
			video_url,
			video_id,
			datetime.utcnow().isoformat(),
		))
		conn.commit()


def count_today_youtube_403() -> int:
	today = datetime.utcnow().date().isoformat()

	with get_conn() as conn:
		cur = conn.execute("""
			SELECT COUNT(*)
			FROM youtube_errors
			WHERE error_type = '403'
			AND DATE(created_at) = ?
		""", (today,))
		return cur.fetchone()[0]

