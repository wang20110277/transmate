FROM python:3.12-slim

WORKDIR /app

# Playwright/Chromium 与部分科学计算依赖需要的基础库
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# store/ 存放 agent checkpoint 与 Chroma 向量库，运行时生成、git-ignored
RUN mkdir -p store && chmod 777 store

EXPOSE 8000

# 实际入口是仓库根目录的 main.py（此前写成 server:app，容器起不来）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
