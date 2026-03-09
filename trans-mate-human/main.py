import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.llm.agents import base_agent
from app.core.database import init_db
from app.base.auth_routes import router as auth_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    logging.info("正在初始化数据库...")
    init_db()
    logging.info("数据库初始化完成")
    yield
    # 关闭时清理资源
    logging.info("应用关闭，清理资源...")


app = FastAPI(
    title="Meta Human API",
    description="Trans-Meta-Human项目API接口文档",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)

# 创建智能助手代理
base_agent = base_agent.agent


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # 构建message
            message = {"messages": [{"role": "user", "content": data}]}
            result = await base_agent.ainvoke(message)
            response = result["messages"][-1].content
            print(response)
            await websocket.send_text(response)
    except WebSocketDisconnect:
        # 只记录必要断开连接信息，避免大量错误日志
        logging.info("WebSocket连接已断开")
    except Exception as e:
        # 只有在非WebSocketDisconnect的情况下才记录错误日志
        logging.error(f"WebSocket连接发生异常: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            # 如果websocket已经关闭，则忽略关闭操作
            pass
