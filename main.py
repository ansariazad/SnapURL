"""
SnapURL — High-Performance URL Shortener API
Fast link shortening with analytics, click tracking, and QR code generation.
Author: Azad Ansari
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional
import sqlite3
import string
import random
import hashlib
import qrcode
import io
import base64
from datetime import datetime
from collections import Counter
import os

app = FastAPI(
    title="SnapURL",
    description="High-performance URL shortener with analytics and QR codes",
    version="2.0.0",
    contact={"name": "Azad Ansari", "url": "https://ansariazad.github.io"}
)

DB_PATH = "snapurl.db"
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
CHARS = string.ascii_letters + string.digits


# ── Models ──
class URLCreate(BaseModel):
    url: HttpUrl
    custom_code: Optional[str] = None
    expires_days: Optional[int] = None

class URLResponse(BaseModel):
    short_url: str
    original_url: str
    code: str
    qr_code: str
    created_at: str


# ── Database ──
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            click_count INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_code TEXT NOT NULL,
            clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            referer TEXT,
            country TEXT,
            FOREIGN KEY (url_code) REFERENCES urls(code)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_code ON urls(code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks(url_code)")
    conn.commit()
    conn.close()


# ── Helpers ──
def generate_code(length=6):
    return ''.join(random.choices(CHARS, k=length))

def generate_qr(url: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


# ── Routes ──
@app.post("/shorten", response_model=URLResponse, tags=["URLs"])
def shorten_url(data: URLCreate):
    """Create a shortened URL with optional custom code and QR."""
    conn = get_db()

    if data.custom_code:
        code = data.custom_code
        existing = conn.execute("SELECT code FROM urls WHERE code=?", (code,)).fetchone()
        if existing:
            conn.close()
            raise HTTPException(status_code=409, detail="Custom code already taken")
    else:
        code = generate_code()
        while conn.execute("SELECT code FROM urls WHERE code=?", (code,)).fetchone():
            code = generate_code()

    expires_at = None
    if data.expires_days:
        from datetime import timedelta
        expires_at = (datetime.utcnow() + timedelta(days=data.expires_days)).isoformat()

    conn.execute(
        "INSERT INTO urls (code, original_url, expires_at) VALUES (?,?,?)",
        (code, str(data.url), expires_at)
    )
    conn.commit()
    conn.close()

    short_url = f"{BASE_URL}/{code}"
    qr_base64 = generate_qr(short_url)

    return URLResponse(
        short_url=short_url,
        original_url=str(data.url),
        code=code,
        qr_code=f"data:image/png;base64,{qr_base64}",
        created_at=datetime.utcnow().isoformat()
    )


@app.get("/{code}", tags=["Redirect"])
def redirect_url(code: str, request: Request):
    """Redirect short URL to original and track click."""
    conn = get_db()
    row = conn.execute("SELECT * FROM urls WHERE code=?", (code,)).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="URL not found")

    if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        conn.close()
        raise HTTPException(status_code=410, detail="URL has expired")

    # Track click
    conn.execute(
        "INSERT INTO clicks (url_code, ip_address, user_agent, referer) VALUES (?,?,?,?)",
        (code, request.client.host, request.headers.get("user-agent", ""),
         request.headers.get("referer", ""))
    )
    conn.execute("UPDATE urls SET click_count = click_count + 1 WHERE code=?", (code,))
    conn.commit()
    conn.close()

    return RedirectResponse(url=row["original_url"], status_code=307)


@app.get("/api/stats/{code}", tags=["Analytics"])
def get_stats(code: str):
    """Get detailed analytics for a shortened URL."""
    conn = get_db()
    url = conn.execute("SELECT * FROM urls WHERE code=?", (code,)).fetchone()
    if not url:
        conn.close()
        raise HTTPException(status_code=404, detail="URL not found")

    clicks = conn.execute(
        "SELECT * FROM clicks WHERE url_code=? ORDER BY clicked_at DESC LIMIT 100", (code,)
    ).fetchall()

    # Analytics
    hourly = Counter()
    browsers = Counter()
    for click in clicks:
        hour = click["clicked_at"][:13] if click["clicked_at"] else "unknown"
        hourly[hour] += 1
        ua = click["user_agent"] or ""
        if "Chrome" in ua: browsers["Chrome"] += 1
        elif "Firefox" in ua: browsers["Firefox"] += 1
        elif "Safari" in ua: browsers["Safari"] += 1
        else: browsers["Other"] += 1

    conn.close()

    return {
        "code": code,
        "original_url": url["original_url"],
        "total_clicks": url["click_count"],
        "created_at": url["created_at"],
        "expires_at": url["expires_at"],
        "recent_clicks": [dict(c) for c in clicks[:20]],
        "hourly_distribution": dict(hourly),
        "browser_stats": dict(browsers)
    }


@app.get("/api/urls", tags=["URLs"])
def list_urls(page: int = 1, limit: int = 20):
    """List all shortened URLs with click counts."""
    conn = get_db()
    offset = (page - 1) * limit
    rows = conn.execute(
        "SELECT code, original_url, click_count, created_at FROM urls ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
    conn.close()

    return {
        "urls": [dict(r) for r in rows],
        "pagination": {"page": page, "limit": limit, "total": total}
    }


@app.delete("/api/urls/{code}", tags=["URLs"])
def delete_url(code: str):
    """Delete a shortened URL and its analytics."""
    conn = get_db()
    url = conn.execute("SELECT code FROM urls WHERE code=?", (code,)).fetchone()
    if not url:
        conn.close()
        raise HTTPException(status_code=404, detail="URL not found")

    conn.execute("DELETE FROM clicks WHERE url_code=?", (code,))
    conn.execute("DELETE FROM urls WHERE code=?", (code,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "code": code}


@app.on_event("startup")
def startup():
    init_db()


if __name__ == "__main__":
    import uvicorn
    init_db()
    print("🔗 SnapURL starting on http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
