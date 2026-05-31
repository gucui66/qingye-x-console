# Twitter爬虫系统 - Docker镜像

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
# 使用 Debian 官方 chromium/chromedriver，兼容 Intel/Apple 芯片 Mac 上的 Docker Desktop
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    chromium \
    chromium-driver \
    ffmpeg \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 运行时只接受已经构建好的 Vue 产物，避免容器构建时再拉 Node 镜像
RUN test -f /app/static/vue/index.html || (echo "缺少前端构建产物，请先执行: cd frontend && npm install && npm run build" && exit 1)

# 创建必要目录
RUN mkdir -p output data static/screenshots static/vue

# 暴露端口
EXPOSE 5001

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

# 启动命令
CMD ["python", "app.py"]
