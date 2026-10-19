import json
from pathlib import Path
from typing import Any

import pytest
import yaml

spec = pytest.mark.spec
ROOT = Path(__file__).resolve().parents[3]


@spec("DEPLOY-1")
def test_dockerfile_is_lean_non_root_checked_and_migrates_on_start() -> None:
    docker = (ROOT / "Dockerfile").read_text()
    assert "uv sync --frozen --no-dev" in docker
    assert "USER app" in docker and "HEALTHCHECK" in docker and "/ready" in docker
    assert "alembic upgrade head" in docker and "${PORT}" in docker
    ignored = (ROOT / ".dockerignore").read_text().split()
    for path in ("data", "web", "api/tests", ".env", ".venv"):
        assert path in ignored


@spec("DEPLOY-2")
def test_ci_builds_and_boots_the_image() -> None:
    ci: dict[str, Any] = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    steps = "\n".join(s.get("run", "") for s in ci["jobs"]["docker"]["steps"])
    assert all(path in steps for path in ("docker build", "/health", "/ready", "/methodology"))
    assert ci["jobs"]["docker"]["services"]["db"]["image"] == "postgres:16"


@spec("DEPLOY-3")
def test_render_blueprint_keeps_secrets_out_of_git() -> None:
    blueprint: dict[str, Any] = yaml.safe_load((ROOT / "render.yaml").read_text())
    [api] = blueprint["services"]
    assert (api["runtime"], api["plan"], api["healthCheckPath"]) == ("docker", "free", "/ready")
    assert api["autoDeployTrigger"] == "checksPass"
    keys = {v["key"] for v in api["envVars"]}
    assert {"DATABASE_URL", "OFF_CONTACT", "AUTH_JWKS_URL", "AUTH_ISSUER", "AUTH_AUDIENCE"} <= keys
    assert all(v.get("sync") is False and "value" not in v for v in api["envVars"])


@spec("DEPLOY-4")
def test_vercel_uses_the_pinned_pnpm_and_env_is_documented() -> None:
    vercel = (ROOT / "web/vercel.json").read_text()
    assert "corepack enable" in vercel and "--frozen-lockfile" in vercel
    package: dict[str, Any] = json.loads((ROOT / "web/package.json").read_text())
    assert package["engines"]["node"] == "24.x"
    auth = (ROOT / "web/src/lib/auth.ts").read_text()
    assert "max: 2" in auth and "allowExitOnIdle: true" in auth
    example = (ROOT / "web/.env.example").read_text()
    for key in ("API_URL", "BETTER_AUTH_URL", "BETTER_AUTH_SECRET", "AUTH_DATABASE_URL",
                "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):  # fmt: skip
        assert f"{key}=" in example


@spec("DEPLOY-5")
def test_the_guide_covers_every_step() -> None:
    guide = (ROOT / "docs/DEPLOYMENT_GUIDE.md").read_text()
    headings = [
        "## 1. Architecture and limitations",
        "## 2. Prerequisites",
        "## 3. Database: Supabase",
        "## 4. API: Render",
        "## 5. Web: Vercel",
        "## 6. Authentication and Google OAuth",
        "## 7. GitHub Actions and initial data",
        "## 8. Verification",
        "## 9. Rollback and recovery",
    ]
    for heading in headings:
        assert heading in guide
    assert "Session pooler" in guide and "postgresql+asyncpg://" in guide
    assert "no automatic database backups" in guide
    assert "/api/auth/callback/google" in guide
