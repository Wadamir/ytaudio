import os

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
MODER_USER_ID = int(os.getenv("MODER_USER_ID", "0"))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
LOG_TIME = os.getenv("LOG_TIME", "false").strip().lower() in {
	"1",
	"true",
	"yes",
	"on",
}
