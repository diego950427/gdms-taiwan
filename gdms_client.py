import requests
import json
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GDMS_USERNAME = "u11310019@go.utaipei.edu.tw"
GDMS_PASSWORD = "Diego950427@@@"
BASE_URL      = "https://gdms.cwa.gov.tw"
LOGIN_URL     = f"{BASE_URL}/login.php"
CATALOG_API   = f"{BASE_URL}/php/dbconnect/getCatalog.php"
NETWORK_API   = f"{BASE_URL}/php/dbconnect/getNetworkList.php"
STATION_API   = f"{BASE_URL}/php/dbconnect/getStationList.php"
LOCATION_API  = f"{BASE_URL}/php/dbconnect/getLocationList.php"
CHANNEL_API   = f"{BASE_URL}/php/dbconnect/getchannelList.php"
STATION1_API  = f"{BASE_URL}/php/dbconnect/getOneStationChannel.php"


def make_session() -> requests.Session:
    s = requests.Session()
    s.verify = False
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


_session: requests.Session | None = None
_logged_in: bool = False


def get_session() -> requests.Session:
    global _session, _logged_in
    if _session is None or not _logged_in:
        _session = make_session()
        _logged_in = _login(_session)
    return _session


def _login(s: requests.Session) -> bool:
    try:
        resp = s.get(LOGIN_URL, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        hidden: dict[str, str] = {}
        form = soup.find("form")
        if form:
            for inp in form.find_all("input"):
                n = inp.get("name")
                v = inp.get("value", "")
                if n and inp.get("type") not in ["submit", "button"]:
                    hidden[n] = v
        data = {**hidden, "username": GDMS_USERNAME, "password": GDMS_PASSWORD}
        r = s.post(LOGIN_URL, data=data, allow_redirects=True, timeout=15)
        return "logout" in r.text.lower() or "登出" in r.text
    except Exception:
        return False


def ensure_login() -> bool:
    global _logged_in
    s = get_session()
    if not _logged_in:
        _logged_in = _login(s)
    return _logged_in


def fetch_json(url: str, method: str = "GET", data: dict | None = None) -> list | dict | None:
    s = get_session()
    try:
        if method == "POST":
            r = s.post(url, data=data or {}, timeout=30)
        else:
            r = s.get(url, params=data, timeout=30)
        return r.json()
    except Exception:
        return None


# ── 公開函式 ────────────────────────────────────────────────────────────────

def get_networks() -> list:
    result = fetch_json(NETWORK_API)
    return result if isinstance(result, list) else []


def get_stations(network: str = "") -> list:
    result = fetch_json(STATION_API, "POST", {"network": network} if network else {})
    return result if isinstance(result, list) else []


def get_locations(network: str = "", station: str = "") -> list:
    p: dict[str, str] = {}
    if network:
        p["network"] = network
    if station:
        p["station"] = station
    result = fetch_json(LOCATION_API, "POST", p)
    return result if isinstance(result, list) else []


def get_channels(network: str = "", station: str = "", location: str = "") -> list:
    p: dict[str, str] = {}
    if network:
        p["network"] = network
    if station:
        p["station"] = station
    if location:
        p["location"] = location
    result = fetch_json(CHANNEL_API, "POST", p)
    return result if isinstance(result, list) else []


def get_catalog(
    stdate: str,
    sttime: str,
    eddate: str,
    edtime: str,
    min_ml: float | None = None,
    max_ml: float | None = None,
    min_dep: float | None = None,
    max_dep: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
    min_lat: float | None = None,
    max_lat: float | None = None,
    cir_lon: float | None = None,
    cir_lat: float | None = None,
    cir_rad: float | None = None,
) -> list:
    p: dict[str, str] = {
        "stdate": stdate,
        "sttime": sttime,
        "eddate": eddate,
        "edtime": edtime,
    }
    if min_ml is not None:
        p["minML"] = str(min_ml)
    if max_ml is not None:
        p["maxML"] = str(max_ml)
    if min_dep is not None:
        p["minDep"] = str(min_dep)
    if max_dep is not None:
        p["maxDep"] = str(max_dep)
    if min_lon is not None:
        p["minlon"] = str(min_lon)
    if max_lon is not None:
        p["maxlon"] = str(max_lon)
    if min_lat is not None:
        p["minlat"] = str(min_lat)
    if max_lat is not None:
        p["maxlat"] = str(max_lat)
    if cir_lon is not None:
        p["cirlon"] = str(cir_lon)
    if cir_lat is not None:
        p["cirlat"] = str(cir_lat)
    if cir_rad is not None:
        p["cirrad"] = str(cir_rad)

    result = fetch_json(CATALOG_API, "POST", p)
    return result if isinstance(result, list) else []
