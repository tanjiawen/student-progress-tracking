#!/bin/bash
# DeepSeek Gateway 启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="${SCRIPT_DIR}/target/release/deepseek-app-server"
CONFIG="${SCRIPT_DIR}/config.toml"

if [ ! -f "$BINARY" ]; then
    echo "错误: 找不到二进制文件 $BINARY"
    echo "请先运行: cargo build -p deepseek-app-server --release"
    exit 1
fi

if [ ! -f "$CONFIG" ]; then
    echo "错误: 找不到配置文件 $CONFIG"
    exit 1
fi

echo "🚀 启动 DeepSeek Gateway..."
echo "   二进制: $BINARY"
echo "   配置: $CONFIG"
echo ""

# 检查 API Key
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "⚠️ 警告: 环境变量 DEEPSEEK_API_KEY 未设置"
    echo "   请在 .env 文件中配置 API Key"
fi

exec "$BINARY" --host 0.0.0.0 --port 8787 --config "$CONFIG"
