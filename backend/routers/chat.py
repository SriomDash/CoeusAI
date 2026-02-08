from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.llm_service import stream_generate

router = APIRouter(prefix="/chat", tags=["chat"])

GLOBAL_LLM_SEMAPHORE = asyncio.Semaphore(5)


@router.get("/health")
async def chat_health():
    return {"status": "healthy"}


async def _recv_text(websocket: WebSocket) -> Optional[str]:
    msg = await websocket.receive()
    msg_type = msg.get("type")

    if msg_type == "websocket.disconnect":
        return None

    if "text" in msg and msg["text"] is not None:
        return msg["text"].strip()

    if "bytes" in msg and msg["bytes"] is not None:
        return ""

    return ""


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()

    try:
        await websocket.send_json(
            {"message": "connected", "hint": 'send "ping" for pong; otherwise send your prompt'}
        )

        while True:
            user_text = await _recv_text(websocket)
            if user_text is None:
                break

            user_text = (user_text or "").strip()
            if not user_text:
                await websocket.send_json({"message": "Please send a non-empty message."})
                continue

            # WebSocket health checks
            lowered = user_text.lower()
            if lowered == "ping":
                await websocket.send_json({"type": "pong", "status": "healthy"})
                continue
            if lowered in {"health", "status"}:
                await websocket.send_json({"type": "health", "status": "healthy"})
                continue

            async with GLOBAL_LLM_SEMAPHORE:
                try:
                    chunks = []
                    for token in stream_generate(user_text):
                        chunks.append(token)
                        await websocket.send_json({"delta": token})

                    await websocket.send_json({"message": "".join(chunks)})

                except Exception:
                    await websocket.send_json({"message": "connection lost"})
                    await websocket.close(code=1011)
                    return

    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.send_json({"message": "connection lost"})
        finally:
            try:
                await websocket.close(code=1011)
            except Exception:
                pass