# 多阶段构建 DeepSeek Gateway
FROM rust:1.75-slim AS builder

WORKDIR /build
COPY . .
RUN cargo build -p deepseek-app-server --release

# 运行时
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制二进制和配置
COPY --from=builder /build/target/release/deepseek-app-server /app/deepseek-app-server
COPY config.toml /app/config.toml

EXPOSE 8787

ENV RUST_LOG=info

ENTRYPOINT ["/app/deepseek-app-server"]
CMD ["--host", "0.0.0.0", "--port", "8787", "--config", "/app/config.toml"]
