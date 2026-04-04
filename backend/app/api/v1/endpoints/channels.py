from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/{agent_id}/ws")
async def agent_websocket(websocket: WebSocket, agent_id: str):
    """
    WebSocket para el web chat widget.
    Sprint 3: conectar con AgentRuntime real.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Placeholder — en Sprint 3 invoca el AgentRuntime con streaming
            await websocket.send_text(f"[Echo Sprint 3] {data}")
    except WebSocketDisconnect:
        pass
