import asyncio
import base64
import os
import shutil
import socket
import threading
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from aiohttp import web
from playwright.async_api import async_playwright


AUTH_DIR = Path(os.getenv("YOUTUBE_AUTH_DIR", "/storage/auth"))
PROFILE_DIR = AUTH_DIR / "profile"
COOKIES_FILE = AUTH_DIR / "cookies.txt"
INITIAL_COOKIES_FILE = Path(os.getenv("INITIAL_COOKIES_FILE", "/cookies.txt"))
YT_PROXY_TYPE = os.getenv("YT_PROXY_TYPE", "socks5").strip().lower()
if YT_PROXY_TYPE not in {"http", "socks5"}:
    raise ValueError("YT_PROXY_TYPE must be one of: http, socks5")

HTTP_PROXIES = (
    os.getenv("HTTP_PROXY_PRIMARY", "").strip(),
    os.getenv("HTTP_PROXY_SECONDARY", "").strip(),
)
SOCKS_PROXIES = (
    os.getenv(
        "SOCKS_PROXY_PRIMARY",
        os.getenv("YT_PROXY_PRIMARY", "socks5h://ytaudio_net:1080"),
    ).strip(),
    os.getenv(
        "SOCKS_PROXY_SECONDARY",
        os.getenv("YT_PROXY_SECONDARY", "socks5h://ytaudio_net:1081"),
    ).strip(),
)
PREFERRED_PROXY_TYPES = (
    (YT_PROXY_TYPE, "socks5" if YT_PROXY_TYPE == "http" else "http")
)
PROXY_ENDPOINTS = {
    "http": HTTP_PROXIES,
    "socks5": SOCKS_PROXIES,
}
PROXY_ROUTES = [
    (proxy_type, url)
    for proxy_type in PREFERRED_PROXY_TYPES
    for url in PROXY_ENDPOINTS[proxy_type]
    if url
]
API_HOST = os.getenv("YOUTUBE_AUTH_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("YOUTUBE_AUTH_API_PORT", "8081"))

playwright = None
browser = None
context = None
page = None


def start_display():
    os.environ["DISPLAY"] = ":99"
    subprocess.Popen(
        ["Xvfb", ":99", "-screen", "0", "1280x720x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    subprocess.Popen(
        ["fluxbox"],
        env={**os.environ, "DISPLAY": ":99"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.Popen(
        [
            "x11vnc",
            "-display", ":99",
            "-forever",
            "-shared",
            "-nopw",
            "-listen", "0.0.0.0",
            "-rfbport", "5900",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.Popen(
        [
            "websockify",
            "--web=/usr/share/novnc",
            "6080",
            "localhost:5900",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Upstream closed")
        data += chunk
    return data


def connect_via_socks(proxy_url, host, port):
    parsed = urlsplit(proxy_url)
    if parsed.scheme not in {"socks5", "socks5h"} or not parsed.hostname:
        raise ValueError("Invalid SOCKS5 proxy URL")

    upstream = socket.create_connection(
        (parsed.hostname, parsed.port or 1080),
        timeout=20,
    )
    try:
        upstream.sendall(b"\x05\x02\x00\x02")
        version, method = recv_exact(upstream, 2)
        if version != 5:
            raise ConnectionError("Invalid SOCKS5 response")

        if method == 2:
            username = unquote(parsed.username or "").encode()
            password = unquote(parsed.password or "").encode()
            if len(username) > 255 or len(password) > 255:
                raise ValueError("SOCKS5 credentials are too long")
            upstream.sendall(
                b"\x01"
                + bytes([len(username)])
                + username
                + bytes([len(password)])
                + password
            )
            auth_version, auth_status = recv_exact(upstream, 2)
            if auth_version != 1 or auth_status != 0:
                raise ConnectionError("SOCKS5 authentication failed")
        elif method != 0:
            raise ConnectionError("SOCKS5 authentication method rejected")

        encoded_host = host.encode("idna")
        request = (
            b"\x05\x01\x00"
            b"\x03"
            + bytes([len(encoded_host)])
            + encoded_host
            + port.to_bytes(2, "big")
        )
        upstream.sendall(request)
        header = recv_exact(upstream, 4)
        if header[1] != 0:
            raise ConnectionError(f"SOCKS5 connect failed: {header[1]}")

        address_type = header[3]
        if address_type == 1:
            recv_exact(upstream, 4)
        elif address_type == 3:
            recv_exact(upstream, recv_exact(upstream, 1)[0])
        elif address_type == 4:
            recv_exact(upstream, 16)
        else:
            raise ConnectionError("Invalid SOCKS5 address type")
        recv_exact(upstream, 2)
        return upstream, b""
    except Exception:
        upstream.close()
        raise


def connect_via_http_proxy(proxy_url, host, port):
    parsed = urlsplit(proxy_url)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("Invalid HTTP proxy URL")

    upstream = socket.create_connection(
        (parsed.hostname, parsed.port or 80),
        timeout=20,
    )
    try:
        authority = f"{host}:{port}"
        headers = [
            f"CONNECT {authority} HTTP/1.1",
            f"Host: {authority}",
            "Proxy-Connection: Keep-Alive",
        ]
        if parsed.username is not None or parsed.password is not None:
            credentials = (
                f"{unquote(parsed.username or '')}:{unquote(parsed.password or '')}"
            ).encode()
            authorization = base64.b64encode(credentials).decode("ascii")
            headers.append(f"Proxy-Authorization: Basic {authorization}")

        upstream.sendall(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = upstream.recv(4096)
            if not chunk:
                raise ConnectionError("HTTP proxy closed before CONNECT response")
            response.extend(chunk)
            if len(response) > 65536:
                raise ConnectionError("HTTP proxy response headers are too large")

        header, pending_data = bytes(response).split(b"\r\n\r\n", 1)
        status_line = header.split(b"\r\n", 1)[0].decode("ascii", "replace")
        status_parts = status_line.split()
        if len(status_parts) < 2 or status_parts[1] != "200":
            status = status_parts[1] if len(status_parts) > 1 else "unknown"
            raise ConnectionError(f"HTTP proxy CONNECT failed: {status}")
        return upstream, pending_data
    except Exception:
        upstream.close()
        raise


def relay_sockets(left, right):
    def copy(source, destination):
        try:
            while True:
                data = source.recv(65536)
                if not data:
                    break
                destination.sendall(data)
        except (ConnectionError, OSError):
            pass
        finally:
            try:
                source.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    threading.Thread(target=copy, args=(left, right), daemon=True).start()
    copy(right, left)


def start_http_proxy_relay():
    if not PROXY_ROUTES:
        return None

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 1081))
    listener.listen()

    def serve():
        while True:
            client, _ = listener.accept()
            threading.Thread(
                target=handle_http_proxy_connection,
                args=(client,),
                daemon=True,
            ).start()

    threading.Thread(target=serve, daemon=True).start()
    return "http://127.0.0.1:1081"


def handle_http_proxy_connection(client):
    try:
        client.settimeout(20)
        request_line = b""
        while b"\r\n\r\n" not in request_line:
            chunk = client.recv(4096)
            if not chunk:
                return
            request_line += chunk
            if len(request_line) > 65536:
                return

        head, pending_data = request_line.split(b"\r\n\r\n", 1)
        line = head.split(b"\r\n", 1)[0].decode("ascii", "ignore")
        parts = line.split(" ")
        if len(parts) < 2 or parts[0].upper() != "CONNECT":
            client.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return

        host, port_text = parts[1].rsplit(":", 1)
        port = int(port_text)
        upstream = None
        upstream_data = b""
        for proxy_type, proxy_url in PROXY_ROUTES:
            try:
                if proxy_type == "socks5":
                    upstream, upstream_data = connect_via_socks(
                        proxy_url,
                        host,
                        port,
                    )
                else:
                    upstream, upstream_data = connect_via_http_proxy(
                        proxy_url,
                        host,
                        port,
                    )
                break
            except (ConnectionError, OSError, ValueError):
                continue

        if upstream is None:
            raise ConnectionError("All configured YouTube proxy routes failed")

        client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        if pending_data:
            upstream.sendall(pending_data)
        if upstream_data:
            client.sendall(upstream_data)
        client.settimeout(None)
        upstream.settimeout(None)
        relay_sockets(client, upstream)
    except (ConnectionError, OSError, ValueError):
        try:
            client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except OSError:
            pass
    finally:
        try:
            client.close()
        except OSError:
            pass


def proxy_config():
    if not PROXY_ROUTES:
        return None
    return {"server": "http://127.0.0.1:1081"}


def netscape_cookie_line(cookie: dict) -> str:
    domain = cookie["domain"]
    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
    path = cookie.get("path") or "/"
    secure = "TRUE" if cookie.get("secure") else "FALSE"
    expires = int(cookie.get("expires") or 0)
    name = cookie.get("name") or ""
    value = cookie.get("value") or ""
    return f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}"


def sync_initial_cookies():
    if not INITIAL_COOKIES_FILE.exists() or INITIAL_COOKIES_FILE.stat().st_size == 0:
        return
    if (
        COOKIES_FILE.exists()
        and INITIAL_COOKIES_FILE.stat().st_mtime_ns <= COOKIES_FILE.stat().st_mtime_ns
    ):
        return

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file = COOKIES_FILE.with_name(f"{COOKIES_FILE.name}.initial.tmp")
    shutil.copyfile(INITIAL_COOKIES_FILE, tmp_file)
    os.chmod(tmp_file, 0o600)
    os.replace(tmp_file, COOKIES_FILE)


def clear_stale_profile_locks():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        lock_path = PROFILE_DIR / lock_name
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def find_chromium_binary():
    candidates = [
        "/root/.cache/ms-playwright/chromium-1255/chrome-linux-arm64/chrome",
        "/root/.cache/ms-playwright/chromium-1255/chrome-linux/chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def start_manual_chromium():
    binary = find_chromium_binary()
    if not binary:
        raise RuntimeError("Chromium binary not found")

    relay_url = proxy_config()
    args = [
        binary,
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-debugging-port=9222",
        f"--user-data-dir={PROFILE_DIR}",
        "--window-size=1280,720",
    ]
    if relay_url:
        args.append(f"--proxy-server={relay_url['server']}")
        args.append("--proxy-bypass-list=<-loopback>")

    args.append("https://accounts.google.com/")
    return subprocess.Popen(
        args,
        env={**os.environ, "DISPLAY": ":99"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def connect_over_cdp():
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            return await playwright.chromium.connect_over_cdp(
                "http://127.0.0.1:9222"
            )
        except Exception:
            await asyncio.sleep(0.5)
    raise RuntimeError("Chromium CDP endpoint is unavailable")


async def export_cookies():
    if context is None:
        return 0

    cookies = await context.cookies()
    youtube_cookies = [
        cookie for cookie in cookies
        if cookie.get("domain", "").endswith("youtube.com")
        or cookie.get("domain", "").endswith("google.com")
    ]
    if not youtube_cookies:
        raise ValueError("No YouTube or Google cookies found; existing files were kept")

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Netscape HTTP Cookie File",
        "# Exported by youtube-auth browser service",
    ]
    lines.extend(netscape_cookie_line(cookie) for cookie in youtube_cookies)
    content = "\n".join(lines) + "\n"
    tmp_file = COOKIES_FILE.with_suffix(".txt.tmp")
    tmp_file.write_text(content)
    os.chmod(tmp_file, 0o600)
    os.replace(tmp_file, COOKIES_FILE)

    if INITIAL_COOKIES_FILE.resolve() != COOKIES_FILE.resolve():
        INITIAL_COOKIES_FILE.write_text(content)
        os.chmod(INITIAL_COOKIES_FILE, 0o600)
    return len(youtube_cookies)


async def health(request):
    global page
    url = page.url if page else ""
    return web.json_response({
        "status": "running",
        "page_url": url,
        "cookies_file": COOKIES_FILE.exists(),
    })


async def export_handler(request):
    try:
        count = await export_cookies()
        return web.json_response({"ok": True, "cookie_count": count})
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)[:500]}, status=500)


async def main():
    global playwright, browser, context, page

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    clear_stale_profile_locks()

    sync_initial_cookies()

    start_display()
    await asyncio.sleep(1)

    playwright = await async_playwright().start()
    if PROXY_ROUTES:
        start_http_proxy_relay()

    chrome_process = start_manual_chromium()
    browser = await connect_over_cdp()
    contexts = browser.contexts
    context = contexts[0] if contexts else await browser.new_context()
    pages = context.pages
    page = pages[0] if pages else await context.new_page()
    if page.url in {"", "about:blank"}:
        await page.goto(
            "https://accounts.google.com/",
            wait_until="domcontentloaded",
            timeout=30000,
        )

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/export", export_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, API_HOST, API_PORT)
    await site.start()

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
