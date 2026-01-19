import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

DB_PATH = Path("/storage/db/bot.sqlite3")


# --------------------------------------------------
# Connection
# --------------------------------------------------
def get_conn():
	DB_PATH.parent.mkdir(parents=True, exist_ok=True)
	conn = sqlite3.connect(DB_PATH)
	conn.execute("PRAGMA foreign_keys = ON;")
	return conn



# --------------------------------------------------
# Helpers
# --------------------------------------------------
def utc_now_iso() -> str:
	return datetime.now(timezone.utc).isoformat()


def utc_today_iso() -> str:
	return datetime.now(timezone.utc).date().isoformat()



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

				registered_at TEXT NOT NULL,
				last_seen TEXT NOT NULL,

				plan TEXT DEFAULT 'standard',
				-- standard | premium | vip | trial
				daily_limit INTEGER DEFAULT 20,
				plan_expires_at TEXT,

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

				processing_mode TEXT,
				-- fast | slow
				processing_time_ms INTEGER,

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

		# --- Indexes ---
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_youtube_errors_type_date
			ON youtube_errors (error_type, created_at)
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_downloads_created_at
			ON downloads (created_at)
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_downloads_user_id
			ON downloads (user_id)
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_downloads_status
			ON downloads (status)
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_users_registered_at
			ON users (registered_at)
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_users_last_seen
			ON users (last_seen)
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_users_downloads_count
			ON users (downloads_count)
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_users_plan
			ON users (plan);
		""")
		conn.execute("""
			CREATE INDEX IF NOT EXISTS idx_users_plan_expires
			ON users (plan_expires_at);
		""")

		conn.commit()



# --------------------------------------------------
# Users
# --------------------------------------------------
def register_user(user) -> None:
	now = utc_now_iso()

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
					registered_at,
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


def get_users() -> list[dict]:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT
				user_id,
				username,
				first_name,
				last_name,
				registered_at,
				last_seen,
				downloads_count,
				last_video_at
			FROM users
		""")
		rows = cur.fetchall()
		users = []
		for row in rows:
			users.append({
				"user_id": row[0],
				"username": row[1],
				"first_name": row[2],
				"last_name": row[3],
				"registered_at": row[4],
				"last_seen": row[5],
				"downloads_count": row[6],
				"last_video_at": row[7],
			})
		return users


def get_total_new_users_today() -> int:
	now = utc_today_iso()
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT COUNT(*)
			FROM users
			WHERE DATE(registered_at) = ?
		""", (now,))
		return cur.fetchone()[0]
	

def get_total_users_week() -> int:
	now = utc_today_iso()
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT COUNT(*)
			FROM users
			WHERE DATE(registered_at) >= DATE(?, '-7 days')
		""", (now,))
		return cur.fetchone()[0]


def get_top_users(limit: int = 10) -> list[dict]:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT
				user_id,
				username,
				first_name,
				last_name,
				downloads_count
			FROM users
			ORDER BY downloads_count DESC
			LIMIT ?
		""", (limit,))
		rows = cur.fetchall()
		users = []
		for row in rows:
			users.append({
				"user_id": row[0],
				"username": row[1],
				"first_name": row[2],
				"last_name": row[3],
				"downloads_count": row[4],
			})
		return users



# --------------------------------------------------
# User plan management
# --------------------------------------------------
def get_user_downloads_today(user_id: int, conn=None) -> int:
	if conn is None:
		with get_conn() as conn:
			return get_user_downloads_today(user_id, conn)

	today = utc_today_iso()
	cur = conn.execute("""
		SELECT COUNT(*)
		FROM downloads
		WHERE user_id = ?
			AND status = 'success'
			AND DATE(created_at) = ?
	""", (user_id, today))
	return cur.fetchone()[0]


def _normalize_user_plan_if_needed(conn, user_id: int) -> None:
	"""
	Normalize user plan if expired.
	Uses caller transaction (do not commit here).
	"""	
	now = utc_now_iso()
	conn.execute("""
		UPDATE users
		SET
			plan = 'standard',
			daily_limit = 20,
			plan_expires_at = NULL
		WHERE user_id = ?
			AND plan_expires_at IS NOT NULL
			AND plan_expires_at < ?
	""", (user_id, now))


def can_user_download(user_id: int) -> tuple[bool, int, int, str]:
	with get_conn() as conn:
		_normalize_user_plan_if_needed(conn, user_id)

		cur = conn.execute("""
			SELECT daily_limit, plan
			FROM users
			WHERE user_id = ?
		""", (user_id,))
		row = cur.fetchone()

		if not row:
			return False, 0, 0, "unknown"

		daily_limit, plan = row
		used_today = get_user_downloads_today(user_id, conn)

		return used_today < daily_limit, used_today, daily_limit, plan



# --------------------------------------------------
# Downloads
# --------------------------------------------------
def increment_downloads(user_id: int) -> None:
	now = utc_now_iso()

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

	processing_mode: Optional[str],
	processing_time_ms: Optional[int],

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
				processing_mode,
				processing_time_ms,
				delivery_method,
				status,
				file_path,
				download_url,
				fallback_reason,
				error_message,
				created_at
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		""", (
			user_id,
			video_url,
			video_id,
			video_title,
			duration_seconds,
			chosen_bitrate,
			estimated_size_mb,
			real_size_mb,
			processing_mode,
			processing_time_ms,
			delivery_method,
			status,
			file_path,
			download_url,
			fallback_reason,
			error_message,
			utc_now_iso(),
		))
		conn.commit()


def get_total_downloads(success_only: bool = True) -> int:
	with get_conn() as conn:
		if success_only:
			cur = conn.execute("SELECT COUNT(*) FROM downloads WHERE status = 'success'")
		else:
			cur = conn.execute("SELECT COUNT(*) FROM downloads")
		return cur.fetchone()[0]
	

def get_total_downloads_today() -> int:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT COUNT(*)
			FROM downloads
			WHERE DATE(created_at) = ?
		""", (utc_today_iso(),))
		return cur.fetchone()[0]
	

def get_total_downloads_week() -> int:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT COUNT(*)
			FROM downloads
			WHERE DATE(created_at) >= DATE(?, '-7 days')
		""", (utc_today_iso(),))
		return cur.fetchone()[0]
	

def get_downloads_per_user(user_id: int) -> int:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT COUNT(*)
			FROM downloads
			WHERE user_id = ?
		""", (user_id,))
		return cur.fetchone()[0]
	

def get_downloads_by_delivery_methods() -> dict[str, int]:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT
				delivery_method,
				COUNT(*) as count
			FROM downloads
			GROUP BY delivery_method
		""")
		rows = cur.fetchall()
		methods = {}
		for row in rows:
			methods[row[0]] = row[1]
		return methods	


def get_failure_rate() -> Optional[float]:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT
				SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
				COUNT(*) as total_count
			FROM downloads
		""")
		row = cur.fetchone()
		failed_count = row[0]
		total_count = row[1]

		if total_count == 0:
			return None
		else:
			return (failed_count / total_count) * 100.0



# --------------------------------------------------
# System stats
# --------------------------------------------------
def get_avg_duration_seconds() -> Optional[float]:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT AVG(duration_seconds)
			FROM downloads
			WHERE status = 'success' 
			AND duration_seconds IS NOT NULL
		""")
		result = cur.fetchone()[0]
		return result if result is not None else None


def get_avg_real_size() -> Optional[float]:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT AVG(real_size_mb)
			FROM downloads
			WHERE real_size_mb IS NOT NULL
		""")
		result = cur.fetchone()[0]
		return result if result is not None else None		
	
def get_avg_processing_time() -> Optional[float]:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT AVG(processing_time_ms)
			FROM downloads
			WHERE status = 'success' 
			AND processing_time_ms IS NOT NULL
		""")
		result = cur.fetchone()[0]
		return result if result is not None else None
	
def get_latency_stats() -> dict[str, Optional[float]]:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT
				processing_mode,
				COUNT(*) AS cnt,
				AVG(processing_time_ms) AS avg_ms
			FROM downloads
			WHERE status = 'success'
			AND processing_mode IS NOT NULL
			AND processing_time_ms IS NOT NULL
			GROUP BY processing_mode;
		""")
		rows = cur.fetchall()
		stats = {}
		for row in rows:
			mode = row[0]
			count = row[1]
			avg_ms = row[2]
			stats[mode] = {
				"count": count,
				"avg_processing_time_ms": avg_ms
			}
		return stats



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
			utc_now_iso()
		))
		conn.commit()	


def get_youtube_errors_today(error_type: str) -> list[dict]:
	today = utc_today_iso()

	with get_conn() as conn:
		cur = conn.execute("""
			SELECT
				id,
				error_type,
				video_url,
				video_id,
				created_at
			FROM youtube_errors
			WHERE error_type = ?
			AND DATE(created_at) = ?
		""", (error_type, today))
		rows = cur.fetchall()

		errors = []
		for row in rows:
			errors.append({
				"id": row[0],
				"error_type": row[1],
				"video_url": row[2],
				"video_id": row[3],
				"created_at": row[4],
			})
		return errors


def get_total_youtube_errors() -> int:
	with get_conn() as conn:
		cur = conn.execute("SELECT COUNT(*) FROM youtube_errors")
		return cur.fetchone()[0]	


def get_total_youtube_errors_today() -> int:
	today = utc_today_iso()

	with get_conn() as conn:
		cur = conn.execute("""
			SELECT COUNT(*)
			FROM youtube_errors
			WHERE DATE(created_at) = ?
		""", (today,))
		return cur.fetchone()[0]


def get_youtube_errors_by_type() -> dict[str, int]:
	with get_conn() as conn:
		cur = conn.execute("""
			SELECT
				error_type,
				COUNT(*) as count
			FROM youtube_errors
			GROUP BY error_type
		""")
		rows = cur.fetchall()
		errors = {}
		for row in rows:
			errors[row[0]] = row[1]
		return errors