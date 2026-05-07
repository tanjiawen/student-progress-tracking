# 多阶段构建 DeepSeek Gateway
FROM rust:1.75-slim AS builder

WORKDIR /app
COPY . .
RUN cargo build -p deepseek-app-server --release

# 运行时
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制二进制和配置
COPY --from=builder /app/target/release/deepseek-app-server /usr/local/bin/deepseek-app-server
COPY config.toml /app/config.toml

EXPOSE 8787

ENV RUST_LOG=info

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8787/healthz || exit 1

CMD ["deepseek-app-server", "--host", "0.0.0.0", "--port", "8787", "--config", "/app/config.toml"]
