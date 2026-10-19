from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ofs:ofs@localhost:5432/ofs"
    response_cache_ttl_s: float = 300  # CACHE-2; 0 turns the cache off
    response_cache_max: int = 2000  # CACHE-4
    off_base_url: str = "https://world.openfoodfacts.org"
    off_contact: str = "set-OFF_CONTACT-in-.env"
    off_timeout_s: float = 4.0
    cache_days: int = 30
    usda_base_url: str = "https://api.nal.usda.gov"
    usda_api_key: str = "DEMO_KEY"  # free; a personal api.data.gov key raises the rate limit
    usda_timeout_s: float = 4.0
    off_user: str | None = None  # CONTRIB-9: sharing with OFF is offered only when both are set
    off_password: str | None = None
    contributions_per_hour: int = 20  # CONTRIB-8
    # ACC-3: the web app's Better Auth issues the JWTs the API accepts.
    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    auth_issuer: str = "http://localhost:3000"
    auth_audience: str = "http://localhost:3000"

    @property
    def user_agent(self) -> str:
        return f"FoodTrace/{APP_VERSION} ({self.off_contact})"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
