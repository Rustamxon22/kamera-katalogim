import os
import time
import uuid
import hmac
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin

import httpx
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, field_validator
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "index.html"

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
KATALOG_PIN = os.getenv("KATALOG_PIN", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
COOKIE_NAME = "kamera_catalog_session"
SESSION_MAX_AGE = 30 * 24 * 60 * 60
BUCKET = "camera-photos"
MAX_IMAGE_BYTES = 10 * 1024 * 1024

app = FastAPI(title="Kamera Katalogim API", docs_url=None, redoc_url=None)

# PIN brute-force himoyasi: umumiy va IP bo'yicha cheklov.
failed_global = deque()
failed_by_ip = {}
LOCK_WINDOW = 15 * 60
MAX_ATTEMPTS = 5

def _clean_attempts(q, now):
    while q and now - q[0] > LOCK_WINDOW:
        q.popleft()

def _client_key(request: Request):
    # Render reverse-proxy ortida ishlaganda forwarded IP olinadi.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:80]
    return request.client.host if request.client else "unknown"

def _settings_ready():
    return (
        SUPABASE_URL.startswith("https://")
        and len(SUPABASE_SERVICE_ROLE_KEY) > 30
        and len(SESSION_SECRET) >= 32
        and len(KATALOG_PIN) == 4
        and KATALOG_PIN.isdigit()
    )

def _serializer():
    if len(SESSION_SECRET) < 32:
        raise HTTPException(status_code=503, detail="Server sozlamalari to‘liq emas.")
    return URLSafeTimedSerializer(SESSION_SECRET, salt="kamera-katalog-session-v1")

def _is_authenticated(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        payload = _serializer().loads(token, max_age=SESSION_MAX_AGE)
        return payload.get("ok") is True
    except (BadSignature, SignatureExpired, HTTPException):
        return False

def require_auth(request: Request):
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="PIN-kod bilan qayta kiring.")
    return True

def _check_origin(request: Request):
    origin = request.headers.get("origin")
    if not origin:
        return
    # Bir xil sayt ichidagi so'rovlar; tashqi saytdan cookie bilan so'rov yuborishni to'sadi.
    from urllib.parse import urlparse
    if urlparse(origin).netloc.lower() != request.headers.get("host", "").lower():
        raise HTTPException(status_code=403, detail="So‘rov manbasi ruxsat etilmagan.")

def _sb_headers(extra=None):
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail="Supabase server sozlamalari kiritilmagan.")
    h = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    if extra:
        h.update(extra)
    return h

async def sb_request(method: str, path: str, *, params=None, json=None, content=None, headers=None):
    url = SUPABASE_URL + path
    merged = _sb_headers(headers)
    async with httpx.AsyncClient(timeout=35) as client:
        response = await client.request(method, url, params=params, json=json, content=content, headers=merged)
    if response.status_code >= 400:
        try:
            detail = response.json().get("message") or response.json().get("error") or response.text
        except Exception:
            detail = response.text
        raise HTTPException(status_code=502, detail=f"Bulut bazasi xatosi: {str(detail)[:300]}")
    if not response.content:
        return None
    try:
        return response.json()
    except Exception:
        return response.text

async def make_signed_image(path):
    if not path:
        return None
    encoded = quote(path, safe="/")
    result = await sb_request(
        "POST",
        f"/storage/v1/object/sign/{BUCKET}/{encoded}",
        json={"expiresIn": 3600},
        headers={"Content-Type": "application/json"},
    )
    signed = result.get("signedURL") or result.get("signedUrl")
    if not signed:
        return None
    return urljoin(SUPABASE_URL + "/", signed.lstrip("/"))

async def remove_image(path):
    if not path:
        return
    await sb_request(
        "DELETE",
        f"/storage/v1/object/{BUCKET}",
        json={"prefixes": [path]},
        headers={"Content-Type": "application/json"},
    )

class LoginBody(BaseModel):
    pin: str = Field(min_length=4, max_length=4)

    @field_validator("pin")
    @classmethod
    def pin_digits(cls, value):
        if not value.isdigit():
            raise ValueError("PIN-kod faqat raqamlardan iborat bo‘lishi kerak.")
        return value

class CameraBody(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    brand: str = Field(default="", max_length=60)
    category: str = Field(default="Boshqa", max_length=60)
    price: float = Field(ge=0, le=999999999999)
    currency: str = "UZS"
    notes: str = Field(default="", max_length=700)
    image_path: str | None = None

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, value):
        if value not in ("UZS", "USD"):
            raise ValueError("Valyuta UZS yoki USD bo‘lishi kerak.")
        return value

@app.get("/")
async def index():
    return FileResponse(INDEX_FILE)

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/api/login")
async def login(body: LoginBody, request: Request):
    _check_origin(request)
    if not _settings_ready():
        raise HTTPException(status_code=503, detail="Server hali sozlanmagan. Administrator Render sozlamalarini tekshirishi kerak.")
    now = time.monotonic()
    ip = _client_key(request)
    ip_q = failed_by_ip.setdefault(ip, deque())
    _clean_attempts(failed_global, now)
    _clean_attempts(ip_q, now)
    if len(failed_global) >= MAX_ATTEMPTS or len(ip_q) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Xavfsizlik uchun kirish 15 daqiqaga bloklandi. Keyinroq urinib ko‘ring.")
    if not hmac.compare_digest(body.pin, KATALOG_PIN):
        failed_global.append(now)
        ip_q.append(now)
        # Tarmoq loglariga PIN yozilmaydi.
        raise HTTPException(status_code=401, detail="PIN-kod noto‘g‘ri.")
    failed_global.clear()
    ip_q.clear()
    token = _serializer().dumps({"ok": True, "issued": int(time.time())})
    response = JSONResponse({"ok": True})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=os.getenv("RENDER", "").lower() == "true",
        samesite="strict",
        path="/",
    )
    return response

@app.get("/api/me")
async def me(request: Request):
    return {"authenticated": _is_authenticated(request)}

@app.post("/api/logout")
async def logout(request: Request, _=Depends(require_auth)):
    _check_origin(request)
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict")
    return response

@app.get("/api/cameras")
async def get_cameras(_=Depends(require_auth)):
    rows = await sb_request(
        "GET",
        "/rest/v1/cameras",
        params={"select": "*", "order": "updated_at.desc"},
    )
    cameras = []
    for row in rows or []:
        item = dict(row)
        try:
            item["image_url"] = await make_signed_image(item.get("image_path"))
        except HTTPException:
            item["image_url"] = None
        cameras.append(item)
    return {"cameras": cameras}

@app.post("/api/images")
async def upload_image(request: Request, file: UploadFile = File(...), _=Depends(require_auth)):
    _check_origin(request)
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=415, detail="Faqat JPG, PNG yoki WEBP rasm yuklash mumkin.")
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Rasm hajmi 10 MB dan oshmasligi kerak.")
    if not data:
        raise HTTPException(status_code=400, detail="Rasm fayli bo‘sh.")
    # Frontend rasmlarni JPEG formatiga aylantiradi; server ham JPEG magic bytes ni tekshiradi.
    if not data.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="Rasm JPEG formatida bo‘lishi kerak.")
    path = f"{uuid.uuid4().hex}.jpg"
    await sb_request(
        "POST",
        f"/storage/v1/object/{BUCKET}/{path}",
        content=data,
        headers={"Content-Type": "image/jpeg", "x-upsert": "false", "cache-control": "3600"},
    )
    return {"path": path}

@app.delete("/api/images")
async def delete_uploaded_image(request: Request, path: str, _=Depends(require_auth)):
    _check_origin(request)
    if "/" in path or len(path) > 80:
        raise HTTPException(status_code=400, detail="Rasm manzili noto‘g‘ri.")
    await remove_image(path)
    return {"ok": True}

@app.post("/api/cameras")
async def create_camera(body: CameraBody, request: Request, _=Depends(require_auth)):
    _check_origin(request)
    payload = body.model_dump()
    result = await sb_request(
        "POST",
        "/rest/v1/cameras",
        params={"select": "*"},
        json=payload,
        headers={"Content-Type": "application/json", "Prefer": "return=representation"},
    )
    return {"camera": result[0] if result else None}

@app.patch("/api/cameras/{camera_id}")
async def update_camera(camera_id: str, body: CameraBody, request: Request, _=Depends(require_auth)):
    _check_origin(request)
    old_rows = await sb_request("GET", "/rest/v1/cameras", params={"id": f"eq.{camera_id}", "select": "image_path"})
    if not old_rows:
        raise HTTPException(status_code=404, detail="Kamera topilmadi.")
    payload = body.model_dump()
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await sb_request(
        "PATCH",
        "/rest/v1/cameras",
        params={"id": f"eq.{camera_id}", "select": "*"},
        json=payload,
        headers={"Content-Type": "application/json", "Prefer": "return=representation"},
    )
    old_path = old_rows[0].get("image_path")
    new_path = payload.get("image_path")
    if old_path and old_path != new_path:
        try:
            await remove_image(old_path)
        except HTTPException:
            pass
    return {"camera": result[0] if result else None}

@app.delete("/api/cameras/{camera_id}")
async def delete_camera(camera_id: str, request: Request, _=Depends(require_auth)):
    _check_origin(request)
    old_rows = await sb_request("GET", "/rest/v1/cameras", params={"id": f"eq.{camera_id}", "select": "image_path"})
    result = await sb_request(
        "DELETE",
        "/rest/v1/cameras",
        params={"id": f"eq.{camera_id}", "select": "id"},
        headers={"Prefer": "return=representation"},
    )
    if old_rows and old_rows[0].get("image_path"):
        try:
            await remove_image(old_rows[0]["image_path"])
        except HTTPException:
            pass
    return {"ok": True}

# Serve a simple deployment-friendly static app; no client-side Supabase secret.
