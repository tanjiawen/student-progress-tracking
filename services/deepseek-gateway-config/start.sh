#!/bin/bash
# DeepSeek Gateway 启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="${SCRIPT_DIR}/../deepseek-gateway/target/release/deepseek-app-server"
CONFIG="${SCRIPT_DIR}/config.toml"

if [ ! -f "$BINARY" ]; then
    echo "错误: 找不到二进制文件 $BINARY"
    echo "请先编译 DeepSeek-TUI: cd services/deepseek-gateway && cargo build -p deepseek-app-server --release"
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

exec "$BINARY" --host 0.0.0.0 --port 8787 --config "$CONFIG"
