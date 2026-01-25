TEXTS = {
	"start_choose_language": "🌍 Please choose your language:",
	"language_set": "✅ Language set: English",

    "invalid_link": "❌ Please send a valid link.",

	"queue": "⏳ Task added to queue. Please wait.",
	"reading_info": "🔍 Reading video information…",

    "failed_reading_info": "❌ Failed to read video information.",

	"fast_mode": "⚡ Downloading audio (fast mode) {size_mb:.1f} MB",
	"slow_mode": "⬇️ Downloading audio (re-encoding) {size_mb:.1f} MB{warning_line}",

	"failed_download": "❌ Failed to download audio.",
	"failed_sending_audio": "❌ Failed to send audio.",

    "failed_create_link": "❌ Failed to create download link.",

    "failed_worker": "❌ An error occurred during processing. Please try again later.",

	"daily_limit_reached": (
		"🚫 <b>Daily limit reached</b>\n\n"
		"Plan: <b>{plan}</b>\n"
		"Used today: <b>{used} / {limit}</b>\n\n"
		"⏰ Limit resets in <b>{reset_in}</b>"
	),

    "plan_info": (
        "📦 <b>Your plan</b>\n\n"
        "• Plan: <b>{plan_name}</b>\n"
        "• Daily limit: <b>{limit}</b>\n"
        "• Used today: <b>{used} / {limit}</b>\n"
        "• Reset in: <b>{reset_in}</b>"
    ),

    "plan_limit_reached": (
        "\n\n🚫 <b>Daily limit reached</b>"
    ),

    "plan_info_upgrade": (
        "\n\n✨ Upgrade your plan to increase limits."
    ),


    "warning_patient": "\n\n⏰ Please be patient.",
    "warning_long_video": "\n\n⏰ This is a long video. Please be patient.",
    "warning_large_file": "\n\n⏰ This is a large file. Please be patient.",

    "warning_max_seconds": (
        "⚠️ This video is longer than 2 hours. I will create a download link instead.\n\n"
		"⏰ Please wait, processing may take some time."
    ),

    "warning_too_large_file": (
        "⚠️ This video is too large for Telegram upload. I can create a download link instead.\n\n"
		"⏰ Please wait, processing may take some time."
    ),

    "audio_ready_caption": (
        "\n\n{bot_caption} <b>{bot_username}</b>"
    ),

    "link_created_caption": (
        "✅ <b>Your download link is ready</b>\n\n"
        "🎵 <a href=\"{link}\">{filename}</a>\n\n"
        "⏰ Available for 12 hours\n\n"
        "{bot_caption} <b>{bot_username}</b>"
    ),
}
