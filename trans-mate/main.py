"""
Main application entry point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.llm.router import agent_router
from app.core.database import init_db
from app.core.config import ALLOWED_ORIGINS, CORS_ALLOW_CREDENTIALS
from app.base.auth_routes import router as auth_router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


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


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            logging.info(f"收到WebSocket消息: {data}")
            message = {"messages": [{"role": "user", "content": data}]}
            logging.info(f"处理消息: {message}")
            result = await agent_router.ainvoke(message)
            logging.info(f"路由结果: {result}")

            response = result["messages"][-1].content
            logging.info(f"响应内容: {response}")
            await websocket.send_text(response)
    except WebSocketDisconnect:
        logging.info("WebSocket连接已断开")
    except Exception as e:
        import traceback

        logging.error(f"WebSocket连接发生异常: {e}")
        logging.error(f"完整堆栈: {traceback.format_exc()}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
