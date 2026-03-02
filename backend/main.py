import asyncio
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


async def _fetch_api(client: httpx.AsyncClient, token: str, path: str) -> dict:
    """Fetch a single Console API endpoint. Returns empty dict on failure."""
    try:
        resp = await client.get(
            f"{settings.console_api_url}{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"Console API {path} returned {resp.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Console API {path} failed: {e}")
    return {}


@app.get("/api/metrics")
async def get_metrics():
    """Return sanitized, public-safe metrics. Only counts — no names, IPs, or details."""
    now = time.time()
    if _metrics_cache["data"] and _metrics_cache["expires"] > now:
        return _metrics_cache["data"]

    try:
        token = await _get_token()
    except HTTPException:
        raise HTTPException(502, "Metrics temporarily unavailable")

    async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
        overview, infra, security = await asyncio.gather(
            _fetch_api(client, token, "/api/overview"),
            _fetch_api(client, token, "/api/infrastructure"),
            _fetch_api(client, token, "/api/security"),
        )

    # Extract only the counts needed for the public dashboard — nothing else
    nodes_online = sum(
        1 for n in infra.get("proxmox_nodes", [])
        if n.get("status") == "online"
    )
    nodes_total = len(infra.get("proxmox_nodes", []))

    services_up = sum(
        1 for s in overview.get("health", [])
        if s.get("status") == "healthy"
    )

    compliance = overview.get("compliance", {})
    compliance_pass = compliance.get("pass_count", 0)
    compliance_total = compliance.get("total", 0)

    agents_active = sum(
        1 for a in security.get("wazuh", {}).get("agents", [])
        if str(a.get("status", "")).lower() == "active"
    )

    sanitized = {
        "infrastructure": {
            "nodes_healthy": nodes_online,
            "nodes_total": nodes_total,
            "services_up": services_up,
        },
        "security": {
            "compliance_checks_pass": compliance_pass,
            "compliance_checks_total": compliance_total,
            "agents_active": agents_active,
        },
    }

    _metrics_cache["data"] = sanitized
    _metrics_cache["expires"] = now + settings.metrics_cache_ttl
    return sanitized


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
