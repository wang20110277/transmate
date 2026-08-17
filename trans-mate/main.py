"""
Main application entry point
"""

import asyncio
import json
import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.llm.streaming import stream_agent_events, build_history_messages
from app.core.database import init_db, SessionLocal
from app.core.config import ALLOWED_ORIGINS, CORS_ALLOW_CREDENTIALS
from app.base.auth_routes import router as auth_router
from app.base.chat_routes import router as chat_router
from app.base.asr_routes import router as asr_router
from app.base.tts_routes import router as tts_router
from app.services import chat_service

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("正在初始化数据库...")
    init_db()
    logging.info("数据库初始化完成")

    yield
    logging.info("应用关闭，清理资源...")


app = FastAPI(
    title="Meta Human API",
    description="Trans-Meta-Human项目API接口文档",
    version="1.0.0",
    lifespan=lifespan,
)

origins = (
    [origin.strip() for origin in ALLOWED_ORIGINS.split(",")]
    if ALLOWED_ORIGINS != "*"
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(asr_router)
app.include_router(tts_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}


async def _send_event(websocket: WebSocket, event: dict):
    """推送一条 JSON 事件，连接已断开时静默忽略"""
    try:
        await websocket.send_text(json.dumps(event, ensure_ascii=False, default=str))
    except Exception:
        pass


async def run_agent_stream(
    websocket: WebSocket, user_message: str, conversation_id: int
):
    """执行智能体流式生成，并逐事件推送给客户端"""
    db = SessionLocal()
    try:
        chat_service.add_message(db, conversation_id, "user", user_message)
        records = chat_service.list_messages(db, conversation_id, limit=20)
        history = build_history_messages(records)

        async for event in stream_agent_events(history):
            if event["type"] == "done":
                chat_service.add_message(
                    db,
                    conversation_id,
                    "assistant",
                    event["content"],
                    event.get("tool_events"),
                )
            await _send_event(websocket, event)
    except asyncio.CancelledError:
        logger.info("智能体生成已被中断")
        await _send_event(websocket, {"type": "stopped", "message": "已停止生成"})
        raise
    except Exception as e:
        logger.error(f"智能体流式任务异常: {e}")
        logger.error(f"完整堆栈: {traceback.format_exc()}")
        await _send_event(websocket, {"type": "error", "message": f"服务异常: {e}"})
    finally:
        db.close()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    generation_task: asyncio.Task | None = None
    try:
        while True:
            data = await websocket.receive_text()
            logging.info(f"收到WebSocket消息: {data}")

            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                # 兼容纯文本消息
                payload = {"type": "chat_message", "message": data}

            msg_type = payload.get("type")

            if msg_type == "stop":
                if generation_task and not generation_task.done():
                    generation_task.cancel()
                continue

            if msg_type != "chat_message":
                continue

            user_message = str(payload.get("message", "")).strip()
            if not user_message:
                continue

            # 同一连接同时只允许一个生成任务
            if generation_task and not generation_task.done():
                generation_task.cancel()

            conversation_id = payload.get("conversation_id")
            if not conversation_id:
                db = SessionLocal()
                try:
                    conversation = chat_service.create_conversation(
                        db, payload.get("user_id", "anonymous")
                    )
                    conversation_id = conversation.id
                finally:
                    db.close()
                await _send_event(
                    websocket,
                    {
                        "type": "conversation_created",
                        "conversation_id": conversation_id,
                    },
                )

            generation_task = asyncio.create_task(
                run_agent_stream(websocket, user_message, conversation_id)
            )
    except WebSocketDisconnect:
        logging.info("WebSocket连接已断开")
    except Exception as e:
        logging.error(f"WebSocket连接发生异常: {e}")
        logging.error(f"完整堆栈: {traceback.format_exc()}")
    finally:
        if generation_task and not generation_task.done():
            generation_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
