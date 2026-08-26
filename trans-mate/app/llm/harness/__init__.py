"""
agent harness 包：对外暴露统一工厂
"""
from app.llm.harness.base import AgentHarness

_harness = None


def get_agent_harness() -> AgentHarness:
    """返回 harness 单例（懒加载 DeepAgentHarness，避免模块导入期拉起重量级依赖）"""
    global _harness
    if _harness is None:
        from app.llm.harness.deep_agent_harness import DeepAgentHarness

        _harness = DeepAgentHarness()
    return _harness
