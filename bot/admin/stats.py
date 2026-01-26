import logging
from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

from typing import Optional
from bot.config.app import ADMIN_USER_ID
from bot.db.db import (
	get_total_users,
	get_total_new_users_today,
	get_total_users_week,
	get_top_users,
	get_total_downloads,
	get_total_downloads_today,
	get_total_downloads_week,
	get_downloads_by_delivery_methods,
	get_failure_rate,
	get_avg_processing_time,
	get_latency_stats,
	get_total_youtube_errors,
	get_total_youtube_errors_today,
	get_youtube_errors_by_type,
	get_failed_downloads_last_24h,
)
from bot.utils.format import fmt_int

logger = logging.getLogger(__name__)


def build_admin_stats_text() -> str:
	# --- Users ---
	total_users = get_total_users()
	new_today = get_total_new_users_today()
	new_week = get_total_users_week()
	top_users = get_top_users(5)

	# --- Downloads ---
	total_dl = get_total_downloads(success_only=True)
	dl_today = get_total_downloads_today()
	dl_week = get_total_downloads_week()
	by_delivery = get_downloads_by_delivery_methods()
	failure_rate = get_failure_rate()

	# --- Performance ---
	avg_latency = get_avg_processing_time()
	latency_by_mode = get_latency_stats()

	# --- Errors ---
	total_errors = get_total_youtube_errors()
	errors_today = get_total_youtube_errors_today()
	errors_by_type = get_youtube_errors_by_type()
	errors_downloads = get_failed_downloads_last_24h()

	# --------------------------------------------------
	# Formatting
	# --------------------------------------------------
	lines = []

	lines.append("📊 <b>YT Audio Bot – Admin Stats</b>\n")

	# 👥 Users
	lines.append("👥 <b>Users</b>")
	lines.append(f"• Total: <b>{total_users}</b>")
	lines.append(f"• New today: <b>{new_today}</b>")
	lines.append(f"• New 7d: <b>{new_week}</b>")

	if top_users:
		lines.append("• Top users:")
		for u in top_users:
			name = u["username"] or u["first_name"] or str(u["user_id"])
			lines.append(f"  – {name}: {fmt_int(u['downloads_count'])}")
	lines.append("")

	# 📥 Downloads
	lines.append("📥 <b>Downloads</b>")
	lines.append(f"• Total (success): <b>{fmt_int(total_dl)}</b>")
	lines.append(f"• Today: <b>{fmt_int(dl_today)}</b>")
	lines.append(f"• 7d: <b>{fmt_int(dl_week)}</b>")

	for k, v in by_delivery.items():
		lines.append(f"• {k}: {fmt_int(v)}")

	if failure_rate is not None:
		if failure_rate < 5:
			icon = "🟢"
		elif failure_rate < 10:
			icon = "🟡"
		else:
			icon = "🔴"
		lines.append(
			f"• Failure rate: {icon} <b>{failure_rate:.2f}%</b>"
		)
	lines.append("")

	# ⚡ Performance
	lines.append("⚡ <b>Performance</b>")
	if avg_latency:
		lines.append(
			f"• Avg latency: <b>{fmt_int(avg_latency)} ms</b>"
		)

	for mode, data in latency_by_mode.items():
		mode_label = mode or "unknown"
		lines.append(
			f"• {mode_label}: {fmt_int(data['count'])} | "
			f"avg {fmt_int(data['avg_processing_time_ms'])} ms"
		)
	lines.append("")

	# 🚨 Errors
	lines.append("🚨 <b>YouTube Errors</b>")
	lines.append(f"• Total: <b>{fmt_int(total_errors)}</b>")
	lines.append(f"• Today: <b>{fmt_int(errors_today)}</b>")
	for etype, cnt in sorted(errors_by_type.items()):
		lines.append(f"• HTTP {etype}: {fmt_int(cnt)}")
	if errors_downloads:
		lines.append("• Failed downloads last 24h:")
		for e in errors_downloads[:5]:
			lines.append(f"• {fmt_int(e['count'])} x {e['error'][:80]}")
	else:
		lines.append("")
		lines.append("✅ <b>No errors in last 24h</b>")

	return "\n".join(lines)


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if update.effective_user.id != ADMIN_USER_ID:
		logger.warning(
			"Unauthorized /stats attempt by user %s",
			update.effective_user.id
		)		
		return

	text = build_admin_stats_text()
	await update.message.reply_text(text)