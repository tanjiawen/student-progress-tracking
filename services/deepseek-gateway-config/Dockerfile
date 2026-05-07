# DeepSeek Gateway 运行时镜像
# 需要提前编译好二进制并复制到构建上下文
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY deepseek-app-server /app/deepseek-app-server
COPY config.toml /app/config.toml

EXPOSE 8787

ENV RUST_LOG=info

ENTRYPOINT ["/app/deepseek-app-server"]
CMD ["--host", "0.0.0.0", "--port", "8787", "--config", "/app/config.toml"]
