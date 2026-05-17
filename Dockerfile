FROM python:3.10-slim

WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 如需使用 Playwright 模式，取消下面两行的注释以安装浏览器内核
# RUN pip install playwright
# RUN playwright install chromium --with-deps

# 复制代码并安装项目
COPY . .
RUN pip install -e .

# 默认运行帮助信息，可通过覆盖命令来执行抓取
ENTRYPOINT ["python", "-m", "xscrape"]
CMD ["--help"]
