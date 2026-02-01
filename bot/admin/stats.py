import logging
from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

# from typing import Optional
from bot.config.app import ADMIN_USER_ID

from bot.db.db import (
	get_total_users,
	get_total_new_users_today,
	get_total_active_users_today,
	# get_total_users_week,
	get_top_users,
	get_top_users_today,
	get_total_downloads,
	get_total_downloads_today,
	# get_total_downloads_week,
	get_downloads_by_delivery_methods,
	get_total_failures,
    get_total_failures_today,
	get_failure_rate,
	get_failure_rate_today,
	get_avg_processing_time,
	get_latency_stats,
	get_total_youtube_errors,
	get_total_youtube_errors_today,
	get_youtube_errors_by_type,
	get_failed_downloads_last_24h,
	get_last_successful_download_at,
)
from bot.utils.format import fmt_int
from bot.utils.time import time_ago_from_iso

LABELS = {
	"telegram": "Telegram",
	"telegram_split": "Telegram (split)",
	"failed": "Failed",
	"fast_mode": "Fast mode",
	"slow_mode": "Slow mode",
}

logger = logging.getLogger(__name__)


def build_admin_stats_text() -> str:
	# --- Users ---
	users_total = get_total_users()
	users_today = get_total_new_users_today()
	users_active_today = get_total_active_users_today()
	# new_week = get_total_users_week()
	top_users = get_top_users(5)
	top_users_today = get_top_users_today(5)

	# --- Downloads ---
	total_dl = get_total_downloads(success_only=True)
	dl_today = get_total_downloads_today()
	# dl_week = get_total_downloads_week()
	# by_delivery = get_downloads_by_delivery_methods()
	failure_total = get_total_failures()
	failure_today = get_total_failures_today()
	failure_rate = get_failure_rate_today()
	failure_rate_today = get_failure_rate_today()

	# --- Performance ---
	avg_latency = get_avg_processing_time()
	latency_by_mode = get_latency_stats()

	# --- Errors ---
	total_errors = get_total_youtube_errors()
	errors_today = get_total_youtube_errors_today()
	errors_by_type = get_youtube_errors_by_type()
	errors_downloads = get_failed_downloads_last_24h()

	# --- Activity ---
	last_successful_download_at = get_last_successful_download_at()
	
	# --------------------------------------------------
	# Formatting
	# --------------------------------------------------
	lines = []

	lines.append("📊 <b>Admin Stats</b>\n")

	# 👥 Users
	lines.append("👥 <b>Users</b>")
	lines.append(f"• Total / Today: <b>{users_total} / {users_today}</b>")
	lines.append(f"• Active today: <b>{users_active_today}</b>")

	if top_users_today:
		lines.append("• Top users today:")
		for u in top_users_today:
			name = u["username"] or u["first_name"] or str(u["user_id"])
			lines.append(f"  – {name}: {fmt_int(u['downloads_count'])}")
	lines.append("")

	# 📥 Downloads
	lines.append("📥 <b>Downloads</b>")
	lines.append(f"• Total / Today: <b>{fmt_int(total_dl)} / {fmt_int(dl_today)}</b>")
	lines.append(f"• Failures Total / Today: <b>{fmt_int(failure_total)} / {fmt_int(failure_today)}</b>")

	# for k, v in by_delivery.items():
	# 	label = LABELS.get(k, k)
	# 	lines.append(f"• {label}: {fmt_int(v)}")

	if failure_rate_today is not None:
		if failure_rate_today < 5:
			icon = "🟢"
		elif failure_rate_today < 10:
			icon = "🟡"
		else:
			icon = "🔴"
		lines.append(
			f"• Failure rate today: {icon} <b>{failure_rate_today:.2f}%</b>"
		)
	lines.append("")

	# ⚡ Performance
	lines.append("⚡ <b>Performance</b>")
	if avg_latency:
		lines.append(
			f"• Avg latency: <b>{fmt_int(avg_latency)} ms</b>"
		)

	for mode, data in latency_by_mode.items():
		mode_label = LABELS.get(mode, mode)
		lines.append(
			f"• {mode_label}: {fmt_int(data['count'])} | "
			f"avg {fmt_int(data['avg_processing_time_ms'])} ms"
		)
	lines.append("")

	# 🚨 Errors
	lines.append("🚨 <b>YouTube Errors</b>")
	lines.append(f"• Total / Today: <b>{fmt_int(total_errors)}</b> / <b>{fmt_int(errors_today)}</b>")
	for etype, cnt in sorted(errors_by_type.items()):
		lines.append(f"• HTTP {etype}: {fmt_int(cnt)}")
	if errors_downloads:
		lines.append("• Failed downloads last 24h:")
		for e in errors_downloads[:5]:
			lines.append(f"• {fmt_int(e['count'])} x {e['error'][:80]}")
	else:
		lines.append("✅ <b>No errors in last 24h</b>")
	lines.append("")

	# ⏰ Activity
	lines.append("⏰ <b>Activity</b>")
	if last_successful_download_at:
		lines.append(f"🕒 Last download: <b>{time_ago_from_iso(last_successful_download_at)}</b>")

	return "\n".join(lines)


def build_users_stats_text() -> str:
    # --- Users ---
    users_total = get_total_users()
    users_today = get_total_new_users_today()
    users_active_today = get_total_active_users_today()
    # new_week = get_total_users_week()
    top_users = get_top_users(10)
    top_users_today = get_top_users_today(10)

    # --------------------------------------------------
    # Formatting
    # --------------------------------------------------
    lines = []

    lines.append("👥 <b>Users Stats</b>\n")

    lines.append(f"• Total users: <b>{users_total}</b>")
    lines.append(f"• New users today: <b>{users_today}</b>")
    lines.append(f"• Active users today: <b>{users_active_today}</b>\n")

    if top_users_today:
        lines.append("• Top users today:")
        for u in top_users_today:
            name = u["username"] or u["first_name"] or str(u["user_id"])
            lines.append(f"  – {name}: {fmt_int(u['downloads_count'])}")
        lines.append("")

    if top_users:
        lines.append("• All-time top users:")
        for u in top_users:
            name = u["username"] or u["first_name"] or str(u["user_id"])
            lines.append(f"  – {name}: {fmt_int(u['downloads_count'])}")
        lines.append("")

    return "\n".join(lines)


def build_downloads_stats_text() -> str:
	# --- Downloads ---
	total_dl = get_total_downloads(success_only=True)
	dl_today = get_total_downloads_today()

	failure_total = get_total_failures()
	failure_today = get_total_failures_today()

	failure_rate_today = get_failure_rate_today()

	by_delivery = get_downloads_by_delivery_methods()
	latency_by_mode = get_latency_stats()

	# --------------------------------------------------
	# Formatting
	# --------------------------------------------------
	lines = []

	lines.append("📥 <b>Downloads Stats</b>\n")

	# 📊 Summary
	lines.append("📊 <b>Summary</b>")
	lines.append(f"• Total downloads: <b>{fmt_int(total_dl)}</b>")
	lines.append(f"• Downloads today: <b>{fmt_int(dl_today)}</b>")
	lines.append(f"• Failures (total / today): <b>{fmt_int(failure_total)} / {fmt_int(failure_today)}</b>")

	if failure_rate_today is not None:
		if failure_rate_today < 5:
			icon = "🟢"
		elif failure_rate_today < 10:
			icon = "🟡"
		else:
			icon = "🔴"

		lines.append(
			f"• Failure rate today: {icon} <b>{failure_rate_today:.2f}%</b>"
		)

	lines.append("")

	# 🚚 Delivery methods
	if by_delivery:
		lines.append("🚚 <b>Delivery methods</b>")
		for method, count in by_delivery.items():
			label = LABELS.get(method, method)
			lines.append(f"• {label}: <b>{fmt_int(count)}</b>")
		lines.append("")

	# ⚡ Performance by mode
	if latency_by_mode:
		lines.append("⚡ <b>Processing time by mode</b>")
		for mode, data in latency_by_mode.items():
			mode_label = LABELS.get(mode, mode)
			lines.append(
				f"• {mode_label}: {fmt_int(data['count'])} | "
				f"avg {fmt_int(data['avg_processing_time_ms'])} ms"
			)

	return "\n".join(lines)


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if update.effective_user.id != ADMIN_USER_ID:
		logger.warning(
			"Unauthorized /stats attempt by user %s",
			update.effective_user.id
		)		
		return

	text = build_admin_stats_text()
	await update.message.reply_text(
		text,
		parse_mode="HTML",
		disable_web_page_preview=True,
	)
	

async def users_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        logger.warning(
            "Unauthorized /users_stats attempt by user %s",
            update.effective_user.id
        )		
        return

    text = build_users_stats_text()
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
	
async def downloads_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        logger.warning(
            "Unauthorized /downloads_stats attempt by user %s",
            update.effective_user.id
        )		
        return

    text = build_downloads_stats_text()
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )