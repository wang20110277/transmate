import asyncio
import os
from typing import Dict, Any

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "Qwen/Qwen3-8B")
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "openai")
DEFAULT_API_URL = os.getenv("API_URL")
DEFAULT_API_KEY = os.getenv("API_KEY")


class ModelPool:
    def __init__(self, size: int = 5, model: str = None, provider: str = None, api_url: str = None, api_key: str = None):
        self.size = size
        self.models = []
        self.semaphore = asyncio.Semaphore(size)
        self.current_index = 0
        
        self.model = model or DEFAULT_MODEL
        self.provider = provider or DEFAULT_PROVIDER
        self.api_url = api_url or DEFAULT_API_URL
        self.api_key = api_key or DEFAULT_API_KEY
        
    def initialize_models(self):
        for _ in range(self.size):
            self.models.append(init_chat_model(
                model=self.model,
                model_provider=self.provider,
                base_url=self.api_url,
                api_key=self.api_key,
                temperature=0.1
            ))
    
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
    
    def invoke(self, input_data: Dict[str, Any]):
        model = self._get_model()
        return model.invoke(input_data)
    
    async def ainvoke(self, input_data: Dict[str, Any]):
        async with self.semaphore:
            model = self._get_model()
            if isinstance(input_data, dict) and "messages" in input_data:
                messages = input_data["messages"]
                result = await model.ainvoke(messages)
            else:
                result = await model.ainvoke(input_data)
            return result
