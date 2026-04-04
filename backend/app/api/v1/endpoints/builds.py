from fastapi import APIRouter
router = APIRouter()

@router.get("/{build_id}")
async def get_build(build_id: str) -> dict:
    return {"build_id": build_id, "status": "pending"}
