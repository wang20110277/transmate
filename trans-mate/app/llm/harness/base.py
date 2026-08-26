"""
AgentHarness 抽象基类
上层（streaming/WebSocket）只依赖此接口，未来可替换 harness 实现
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List

from langchain_core.messages import BaseMessage


class AgentHarness(ABC):
    """agent harness 抽象接口"""

    @abstractmethod
    def astream(
        self, history: List[BaseMessage], thread_id: str
    ) -> AsyncGenerator[dict, None]:
        """驱动 agent 执行一轮，产出归一化事件（见 events.py）。

        history 为 DB 拼出的完整消息列表（含本次 user 输入）；
        是否全量注入由实现根据 checkpoint 状态决定。
        实现为 async 生成器函数（async def + yield）。
        """
        raise NotImplementedError

    @abstractmethod
    async def clear_thread(self, thread_id: str) -> None:
        """清除某个会话的持久化状态（会话删除时调用）"""
        raise NotImplementedError

    async def initialize(self) -> None:
        """初始化重量级资源（模型/checkpoint 存储），默认无操作"""

    async def aclose(self) -> None:
        """释放资源（应用关停时调用），默认无操作"""
