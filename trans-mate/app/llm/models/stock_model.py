import asyncio
import os
from typing import Dict, Any

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

DEFAULT_MODEL = os.getenv("KIMI_MODEL", "kimi-k2-turbo-preview")
DEFAULT_PROVIDER = os.getenv("KIMI_PROVIDER", "moonshot")
DEFAULT_API_URL = os.getenv("KIMI_API_URL", "https://api.moonshot.cn/v1")
DEFAULT_API_KEY = os.getenv(
    "KIMI_API_KEY", "sk-pWTf47E87LVhUPFr1eYRtdVCnOUJRHLYY94Vkl7iTi4CP2Cs"
)
DEFAULT_TIMEOUT = int(os.getenv("KIMI_TIMEOUT", "60"))


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

        self.model = model or DEFAULT_MODEL
        self.provider = provider or DEFAULT_PROVIDER
        self.api_url = api_url or DEFAULT_API_URL
        self.api_key = api_key or DEFAULT_API_KEY
        self.timeout = timeout or DEFAULT_TIMEOUT

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
