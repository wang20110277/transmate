"""
Kimi 模型池
"""

import asyncio
from typing import Dict, Any

from langchain.chat_models import init_chat_model

from app.core.config import (
    KIMI_MODEL,
    KIMI_PROVIDER,
    KIMI_API_URL,
    KIMI_API_KEY,
    KIMI_TIMEOUT,
)


def create_crewai_llm():
    """Create a crewai-compatible LLM for use with crewai agents."""
    from crewai import LLM

    return LLM(
        model=KIMI_MODEL,
        provider=KIMI_PROVIDER,
        base_url=KIMI_API_URL,
        api_key=KIMI_API_KEY,
        temperature=0.1,
        timeout=KIMI_TIMEOUT,
    )


class StockModelPool:
    def __init__(
        self,
        size: int = 5,
        model: str = None,
        provider: str = None,
        api_url: str = None,
        api_key: str = None,
        timeout: int = None,
    ):
        self.size = size
        self.models = []
        self.semaphore = asyncio.Semaphore(size)
        self.current_index = 0

        self.model = model or KIMI_MODEL
        self.provider = provider or KIMI_PROVIDER
        self.api_url = api_url or KIMI_API_URL
        self.api_key = api_key or KIMI_API_KEY
        self.timeout = timeout or KIMI_TIMEOUT

    def initialize_models(self):
        for _ in range(self.size):
            self.models.append(
                init_chat_model(
                    model=self.model,
                    model_provider=self.provider,
                    base_url=self.api_url,
                    api_key=self.api_key,
                    temperature=0.1,
                    timeout=self.timeout,
                )
            )

    def bind_tools(self, tools, **kwargs):
        model = self._get_model()
        return model.bind_tools(tools, **kwargs)

    def _get_model(self):
        if self.models:
            model = self.models[self.current_index % len(self.models)]
            self.current_index = (self.current_index + 1) % len(self.models)
            return model
        else:
            self.initialize_models()
            return self._get_model()

    def invoke(self, input_data: Dict[str, Any], timeout: int = None):
        model = self._get_model()
        request_timeout = timeout or self.timeout
        return model.invoke(input_data, timeout=request_timeout)

    async def ainvoke(self, input_data: Dict[str, Any], timeout: int = None):
        async with self.semaphore:
            model = self._get_model()
            request_timeout = timeout or self.timeout
            if isinstance(input_data, dict) and "messages" in input_data:
                messages = input_data["messages"]
                result = await model.ainvoke(messages, timeout=request_timeout)
            else:
                result = await model.ainvoke(input_data, timeout=request_timeout)
            return result
