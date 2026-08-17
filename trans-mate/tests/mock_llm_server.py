"""
Mock OpenAI 兼容服务：用于无真实 API Key 时验证流式与工具调用链路。

行为：
- 最近一条是工具结果，或消息里含工具结果 → 流式返回文本（附历史用户消息数，用于验证多轮上下文）
- 用户消息含"天气" → 返回 get_weather 工具调用
- 其他 → 流式返回普通文本
"""
import json

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI()


def build_response(messages):
    user_count = sum(1 for m in messages if m.get("role") == "user")
    has_tool_result = any(m.get("role") == "tool" for m in messages)
    last = messages[-1] if messages else {}

    if has_tool_result:
        return "text", f"根据工具查询结果，北京今天晴。本次对话共包含{user_count}轮用户消息。"
    if last.get("role") == "user" and "天气" in str(last.get("content", "")):
        return "tool", None
    return "text", f"这是来自Mock LLM的流式回复。本次请求包含{user_count}轮用户消息。"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    kind, text = build_response(messages)

    if not stream:
        if kind == "tool":
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": json.dumps({"city": "北京"}, ensure_ascii=False),
                        },
                    }
                ],
            }
            finish = "tool_calls"
        else:
            message = {"role": "assistant", "content": text}
            finish = "stop"
        return JSONResponse(
            {
                "id": "mock",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )

    def sse():
        if kind == "tool":
            first = {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "get_weather", "arguments": ""},
                                }
                            ],
                        },
                        "finish_reason": None,
                    }
                ]
            }
            yield f"data: {json.dumps(first)}\n\n"
            args_chunk = {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {
                                        "arguments": json.dumps({"city": "北京"}, ensure_ascii=False)
                                    },
                                }
                            ],
                        },
                        "finish_reason": None,
                    }
                ]
            }
            yield f"data: {json.dumps(args_chunk)}\n\n"
        else:
            for ch in text:
                chunk = {
                    "choices": [{"index": 0, "delta": {"content": ch}, "finish_reason": None}]
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        done = {
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls" if kind == "tool" else "stop",
                }
            ]
        }
        yield f"data: {json.dumps(done)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9100, log_level="warning")
