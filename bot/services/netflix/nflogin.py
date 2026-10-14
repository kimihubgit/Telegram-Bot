"""
Netflix NFToken Login — Service
Lấy token đăng nhập Netflix từ cookie NetflixId qua iOS API.
Trả về link: https://netflix.com/?nftoken=<token>
"""
import json
import re
import urllib.parse
from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# ── API config ────────────────────────────────────────────────
_API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"

_QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

_BASE_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

_COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")


# ── Cookie parsing ────────────────────────────────────────────

def _decode_value(value: str) -> str:
    if isinstance(value, str) and "%" in value:
        try:
            return urllib.parse.unquote(value)
        except Exception:
            pass
    return value


def extract_netflix_id_from_file(filepath: str) -> str | None:
    """
    Đọc file cookie (Netscape .txt, JSON array, JSON object, hoặc cookie string)
    và trả về giá trị NetflixId.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read().strip()
    except Exception:
        return None

    if not text:
        return None

    cookie_dict: dict = {}

    # Thử Netscape format (tab-separated)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookie_dict[parts[5]] = parts[6]

    # Thử JSON
    if not cookie_dict.get("NetflixId"):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    name = item.get("name")
                    if name in _COOKIE_KEYS:
                        cookie_dict[name] = _decode_value(item.get("value", ""))
            elif isinstance(data, dict):
                if any(k in data for k in _COOKIE_KEYS):
                    for k in _COOKIE_KEYS:
                        if k in data:
                            cookie_dict[k] = _decode_value(data[k])
                elif isinstance(data.get("cookies"), list):
                    for item in data["cookies"]:
                        name = item.get("name")
                        if name in _COOKIE_KEYS:
                            cookie_dict[name] = _decode_value(item.get("value", ""))
        except Exception:
            pass

    # Thử regex từ cookie string dạng key=value; key=value
    if not cookie_dict.get("NetflixId"):
        for key in _COOKIE_KEYS:
            match = re.search(rf"(?<!\w){re.escape(key)}=([^;,\s]+)", text)
            if match:
                cookie_dict[key] = _decode_value(match.group(1))

    return cookie_dict.get("NetflixId")


# ── Token fetching ────────────────────────────────────────────

def fetch_nftoken(netflix_id: str) -> tuple[str, int | None]:
    """
    Gọi Netflix iOS API để lấy nftoken.
    Trả về (token, expires_timestamp) hoặc raise exception nếu thất bại.
    """
    headers = dict(_BASE_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    response = requests.get(
        _API_URL,
        params=_QUERY_PARAMS,
        headers=headers,
        timeout=30,
        verify=False,
    )
    response.raise_for_status()

    data = response.json()
    token_data = (
        (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default")
        or {}
    )

    token = token_data.get("token")
    expires = token_data.get("expires")

    if not token:
        raise ValueError("Không tìm thấy token trong response.")

    # Chuyển milliseconds → seconds nếu cần
    if isinstance(expires, int) and len(str(expires)) == 13:
        expires //= 1000

    return token, expires


def build_login_url(token: str) -> str:
    return f"https://netflix.com/?nftoken={token}"


def format_expiry(expires) -> str:
    if not isinstance(expires, (int, float)):
        return "Không rõ"
    try:
        return datetime.fromtimestamp(expires).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(expires)
