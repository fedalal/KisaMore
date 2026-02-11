from fastapi import APIRouter, HTTPException
from . import runtime

router = APIRouter(prefix="/api", tags=["inputs"])

@router.get("/inputs")
async def get_inputs():
    if not runtime.inputs:
        raise HTTPException(500, "inputs not initialized")
    return {
        "ok": True,
        "levels": runtime.inputs.snapshot()
    }
