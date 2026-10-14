"""
Netflix Service — TV Code Activation
Chứa toàn bộ logic kích hoạt mã TV Netflix qua cookie.
"""
import os
import re
from pathlib import Path
from urllib.parse import unquote

import requests

# ==================== CONFIG ====================
COOKIE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)

USED_COOKIE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "cookies_used"
USED_COOKIE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)
TIMEOUT = 20
# ================================================


def parse_netscape_cookies(filepath: str) -> str | None:
    """
    Đọc file cookie dạng Netscape (tab-separated) và trả về cookie string.
    Bỏ qua các dòng metadata ở đầu file (không có tab).
    Trả về None nếu không parse được cookie nào.
    """
    cookies = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    name = parts[5]
                    value = parts[6]
                    cookies.append(f"{name}={value}")
    except Exception:
        return None

    return "; ".join(cookies) if cookies else None


def extract_account_info(text: str) -> dict:
    """Trích xuất thông tin tài khoản Netflix từ HTML."""
    patterns = {
        "plan": r'"localizedPlanName"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"',
        "email": r'"emailAddress"\s*:\s*"([^"]+)"',
        "country": r'"countryOfSignup"\s*:\s*"([^"]+)"',
    }
    result = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        result[key] = match.group(1) if match else None
    return result


def check_cookie_live(cookie_string: str) -> dict:
    """
    Kiểm tra cookie Netflix còn sống không.
    Trả về dict: {"live": True/False, "info": {...}}
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for pair in cookie_string.split("; "):
        if "=" in pair:
            name, value = pair.split("=", 1)
            session.cookies.set(name, value, domain=".netflix.com")

    try:
        response = session.get("https://www.netflix.com/YourAccount", timeout=TIMEOUT)
        response.raise_for_status()
        html = response.text

        if "Sign In" in html or "Sign in" in html:
            return {"live": False, "info": None}

        info = extract_account_info(html)
        return {"live": True, "info": info}

    except Exception:
        return {"live": False, "info": None}


def activate_tv_code(cookie_string: str, tv_code: str) -> dict:
    """
    Kích hoạt mã TV trên Netflix bằng cookie.
    Trả về dict: {"status": "success"|"fail"|"error", "message": str}
    """
    session = requests.Session()
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://www.netflix.com',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'referer': 'https://www.netflix.com/tv8',
        'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-model': '"Nexus 5"',
        'sec-ch-ua-platform': '"Android"',
        'sec-ch-ua-platform-version': '"6.0"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36',
    }

    for pair in cookie_string.split("; "):
        if "=" in pair:
            name, value = pair.split("=", 1)
            session.cookies.set(name, value, domain=".netflix.com")

    try:
        # Bước 1: Truy cập /tv8 để lấy authURL (CSRF Token)
        response = session.get("https://www.netflix.com/tv8", headers=headers, timeout=TIMEOUT)
        if response.status_code != 200:
            print("Không thể truy cập netflix.com")
            return {"status": "error", "message": f"Không thể truy cập Netflix. HTTP {response.status_code}"}

        auth_url_match = re.search(r'"authURL":"([^"]+)"', response.text)
        if not auth_url_match:
            print("Không tìm thấy authURL")
            return {"status": "error", "message": "Không tìm thấy authURL. Cookie có thể đã hết hạn."}

        auth_url = auth_url_match.group(1)
        auth_url = unquote(auth_url)
        auth_url = auth_url.replace('\\x2B', '+').replace('\\x3D', '=')
        print("AuthURL sau decode:", auth_url)

        # Bước 2: POST để kích hoạt mã TV
        payload = {
            "flow": "websiteSignUp",
            "authURL": auth_url,
            "flowMode": "enterTvLoginRendezvousCode",
            "withFields": "tvLoginRendezvousCode,isTvUrl2",
            "code": tv_code,
            "tvLoginRendezvousCode": tv_code,
            "action": "nextAction",
        }

        post_response = session.post(
            "https://www.netflix.com/tv8",
            headers=headers,
            data=payload,
            timeout=TIMEOUT,
        )
        print(post_response.text)

        if "success" in post_response.text.lower() or post_response.status_code == 200:
            return {"status": "success", "message": "Kích hoạt TV thành công!"}
        else:
            return {"status": "fail", "message": "Kích hoạt thất bại. Mã code có thể sai hoặc đã hết hạn."}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_available_cookies() -> list[str]:
    """Lấy danh sách file cookie có sẵn trong kho."""
    if not COOKIE_DIR.exists():
        return []
    return [
        str(COOKIE_DIR / f)
        for f in os.listdir(COOKIE_DIR)
        if f.endswith((".txt", ".json")) and os.path.isfile(COOKIE_DIR / f)
    ]
