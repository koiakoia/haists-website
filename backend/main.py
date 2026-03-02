import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from config import Settings

settings = Settings()
logger = logging.getLogger("haists-website")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_metrics_cache: dict = {"data": None, "expires": 0}
_token_cache: dict = {"token": None, "expires": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Haists website starting")
    yield
    logger.info("Haists website shutting down")


app = FastAPI(title="Haists IT Consulting", lifespan=lifespan)


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


async def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires"] > now:
        return _token_cache["token"]

    if not settings.oidc_client_secret:
        raise HTTPException(503, "OIDC not configured")

    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            f"{settings.oidc_issuer}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
            },
        )
        if resp.status_code != 200:
            logger.error(f"Token request failed: {resp.status_code}")
            raise HTTPException(503, "Authentication failed")

        data = resp.json()
        _token_cache["token"] = data["access_token"]
        _token_cache["expires"] = now + data.get("expires_in", 300) - 30
        return _token_cache["token"]


@app.get("/api/metrics")
async def get_metrics():
    now = time.time()
    if _metrics_cache["data"] and _metrics_cache["expires"] > now:
        return _metrics_cache["data"]

    try:
        token = await _get_token()
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(
                f"{settings.console_api_url}/api/health",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                logger.warning(f"Console API returned {resp.status_code}")
                raise HTTPException(502, "Upstream unavailable")

            raw = resp.json()
    except httpx.RequestError as e:
        logger.error(f"Console API request failed: {e}")
        raise HTTPException(502, "Upstream unreachable")

    sanitized = {
        "infrastructure": {
            "nodes_healthy": _count_healthy(raw.get("proxmox", {})),
            "services_up": _count_services(raw),
            "uptime_pct": 99.9,
        },
        "security": {
            "compliance_score": raw.get("compliance", {}).get("pass_rate", 0),
            "agents_active": raw.get("wazuh", {}).get("agents", {}).get("active", 0),
        },
        "cached_at": int(now),
    }

    _metrics_cache["data"] = sanitized
    _metrics_cache["expires"] = now + settings.metrics_cache_ttl
    return sanitized


def _count_healthy(proxmox_data: dict) -> int:
    nodes = proxmox_data.get("nodes", [])
    if isinstance(nodes, list):
        return sum(1 for n in nodes if n.get("status") == "online")
    return 0


def _count_services(health_data: dict) -> int:
    count = 0
    for val in health_data.values():
        if isinstance(val, dict) and val.get("status") in ("healthy", "ok", "online"):
            count += 1
    return count


@app.post("/api/contact")
async def contact(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    name = payload.get("name", "").strip()
    email = payload.get("email", "").strip()
    message = payload.get("message", "").strip()

    if not name or not email or not message:
        raise HTTPException(422, "Name, email, and message are required")

    if "@" not in email or "." not in email:
        raise HTTPException(422, "Invalid email address")

    bot_payload = {
        "name": name,
        "email": email,
        "company": payload.get("company", ""),
        "interest": payload.get("interest", ""),
        "message": message,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.matrix_bot_url}/contact",
                json=bot_payload,
            )
            if resp.status_code != 200:
                logger.error(f"Matrix bot returned {resp.status_code}")
                raise HTTPException(502, "Failed to send message")
    except httpx.RequestError as e:
        logger.error(f"Matrix bot request failed: {e}")
        raise HTTPException(502, "Contact service unavailable")

    return {"status": "sent", "message": "Thank you for your inquiry. We'll be in touch soon."}


# Mount static files last (catch-all)
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
