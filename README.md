# 🔗 SnapURL — URL Shortener with Analytics

High-performance URL shortener API with click tracking, QR code generation, and detailed analytics.

## Features

- 🔗 **URL Shortening** — Generate short codes or use custom aliases
- 📊 **Click Analytics** — Track every click with IP, browser, timestamp
- 📱 **QR Code Generation** — Auto-generate QR codes for every short URL
- ⏰ **Expiration** — Set auto-expiry in days
- 📈 **Dashboard Data** — Hourly distribution, browser stats, recent clicks
- ⚡ **Fast** — SQLite with indexed lookups, 307 redirects

## Tech Stack

- **Framework:** FastAPI (Python)
- **Database:** SQLite (indexed)
- **QR Codes:** qrcode + Pillow
- **Docs:** Swagger/OpenAPI (auto-generated)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/shorten` | Create short URL (+ QR code) |
| GET | `/{code}` | Redirect to original URL |
| GET | `/api/stats/{code}` | Click analytics & browser stats |
| GET | `/api/urls` | List all URLs (paginated) |
| DELETE | `/api/urls/{code}` | Delete URL + analytics |

## Quick Start

```bash
pip install fastapi uvicorn qrcode pillow
python main.py
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

## Example

```bash
# Shorten a URL
curl -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/ansariazad", "custom_code": "github"}'

# Response includes short_url + QR code (base64)
```

## Author

**Azad Ansari** — [Portfolio](https://ansariazad.github.io) · [GitHub](https://github.com/ansariazad)
