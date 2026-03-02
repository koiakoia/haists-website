from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Overwatch Console API (for metrics proxy)
    console_api_url: str = "https://console-sec.208.haist.farm"

    # Keycloak OIDC (client_credentials for Console API)
    oidc_issuer: str = "https://auth.208.haist.farm/realms/sentinel"
    oidc_client_id: str = "haists-website"
    oidc_client_secret: str = ""

    # Matrix bot (for contact form)
    matrix_bot_url: str = "http://10.0.0.1:9095"

    # Contact settings
    contact_recipient_email: str = ""

    # Cache TTL for metrics (seconds)
    metrics_cache_ttl: int = 300

    model_config = {"env_prefix": "HW_"}
