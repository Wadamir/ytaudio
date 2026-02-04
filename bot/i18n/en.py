TEXTS = {
	"start_choose_language": "🌍 Please choose your language:",
	"language_set": "✅ Language set: English 🇬🇧",    
    "after_language_set": "Now send me a YouTube link\nor you can use the menu below 👇",
    "language_set_default": "Language set to English 🇬🇧",

    "start_welcome_new": "Welcome, friend! 👋\nPlease choose your language below 👇",
    "start_welcome_back": "Welcome back, my friend! 👋",

	"queue": "⏳ Task added to queue. Please wait.",
	"reading_info": "🔍 Reading video information…",

    "info_ready": "✅ Video information ready. Duration: {duration}\n⬇️ Proceeding to download audio…",

	"fast_mode": "⚡ Downloading audio (fast mode) Duration: {duration}...",
	"slow_mode": "⬇️ Downloading audio (re-encoding) Duration: {duration}... Please be patient...",

    "job_completed": "✅ Your job has been completed successfully.",


    "unsupported_platform": "❌ Please send a valid link.",
    "video_unavailable": "❌ Video is unavailable.",
    "live_not_supported": "❌ Live streams are not supported.",
    "video_too_long": "❌ Sorry, the video duration exceeds the maximum allowed length of {max_duration}. Please try a shorter video.",
    "failed_reading_info": "❌ Sorry, failed to read video information.",    
	"failed_download": "❌ Failed to download audio. Please try again later....",

    "failed_processing": "❌ Failed to process audio. Please try again later.",
    "file_too_large": "❌ The resulting file is too large for Telegram upload.",
	"failed_sending_audio": "❌ Failed to send audio. Please try again later.",
    "failed_create_link": "❌ Failed to create download link.",


    "failed_worker": "❌ An error occurred during processing. Please try again later.",

	"daily_limit_reached": (
		"🚫 <b>Daily limit reached</b>\n\n"
		"Plan: <b>{plan}</b>\n"
		"Used today: <b>{used} / {limit}</b>\n\n"
		"⏰ Limit resets in <b>{reset_in}</b>"
	),

    "supporter_info": (
        "🌟 <b>Supporter!</b>\nThank you for your support! Your contributions help keep the bot running and improve its features.\n\n"
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
        "\n\n{bot_caption_prefix} <b>{bot_username}</b>"
    ),

    "link_created_caption": (
        "✅ <b>Your download link is ready</b>\n\n"
        "🎵 <a href=\"{link}\">{filename}</a>\n\n"
        "⏰ Available for 12 hours\n\n"
        "{bot_caption_prefix} <b>{bot_username}</b>"
    ),

    # --- Help text ---
    "help_text": (
        "❓ <b>Help & FAQ</b>\n\n"
        "• To download audio, simply send me a YouTube link.\n"
        "• You can check your plan and usage with the '💳 Plan' button.\n"
        "• To change the language, use the '🌐 Language' button.\n\n"
        "If you have any other questions, feel free to ask!"
    ),

    # --- Donation ---
    "donate_prompt": "⭐ Support the bot ⭐\n\nIf you like this bot, you can support its development by donating stars! Your support helps keep the bot running and improves its features.\n\nChoose a donation amount below:",
    
    "donate_10_stars": "⭐ Small tip (10 ⭐)",
    "donate_100_stars": "⭐ Supporter (100 ⭐)",
    "donate_300_stars": "⭐ Big thanks (300 ⭐)",
    "donate_500_stars": "⭐ Premium donation (500 ⭐)",
    
    "donation_title": "Support the bot ⭐",
    "donation_description": "If you like this bot, you can support development ❤️",
    "donation_thanks": "❤️ Thank you for your support!\nYou donated {stars} ⭐",

    # --- Keyboards ---
    "menu_hint": "You can use the menu below 👇",
    "btn_language": "🌐 Language",
    "btn_plan": "💳 Plan",
    "btn_help": "❓ Help",
    "btn_donate": "⭐ Donate",
}
