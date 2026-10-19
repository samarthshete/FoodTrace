"""`GET /methodology`: the numbers behind the score, straight from the config (specs/019)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.scoring.config import ScoringConfig, default_config

router = APIRouter(tags=["methodology"])


@router.get("/methodology")
async def methodology(
    response: Response, cfg: Annotated[ScoringConfig, Depends(default_config)]
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=3600"  # METH-1
    add, proc = cfg.additives, cfg.processing
    return {
        "engine_version": cfg.engine_version,
        "weights": cfg.weights,
        "bands": [b.model_dump() for b in cfg.bands],
        "nova_values": {str(k): v for k, v in proc.nova_values.items()},
        "additives": {
            "risk_penalty": {str(k): v for k, v in add.risk_penalty.items()},
            "evidence_weight": add.evidence_weight,
            "cap_total": add.cap_total,
        },
        "sources": {
            "nutriscore_foods": cfg.nutriscore.source_urls["foods"],
            "nutriscore_beverages": cfg.nutriscore.source_urls["beverages"],
            "efsa": add.efsa_source,
            "nova": proc.source_url,
        },
        "changelog": [e.model_dump() for e in cfg.changelog],  # METH-2
    }
