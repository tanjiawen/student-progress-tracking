# DeepSeek TUI 服务化封装 — 目标机器安装操作手册

> 适用: macOS (ARM64 / x64) · Linux (glibc x64) · Windows (x64)  
> 版本: v0.8.14  
> 前提: 已获得 DeepSeek API Key  
> 🆕 完全离线安装 — deploy/bin/ 内置 4 个平台二进制

---

## 概览

4 步完成。安装脚本自动检测平台，选择对应二进制。

| 步骤 | macOS / Linux | Windows | 时间 |
|------|--------------|---------|------|
| 1 | 拷贝 `deploy/` 到目标机器 | 同左 | 1 min |
| 2 | ~~安装二进制~~ 已内置 | 同左 | 0 |
| 3 | 配置 API Key | 同左 | 1 min |
| 4 | `./install-service.sh --with-bridge` | `install-service.ps1 -WithBridge` | 2 min |
| 5 | 验证服务 | 同左 | 1 min |

`deploy/bin/` 已内置 v0.8.14 二进制:

| 目录 | 平台 |
|------|------|
| `bin/macos-arm64/` | macOS Apple Silicon |
| `bin/macos-x64/` | macOS Intel |
| `bin/linux-x64/` | Linux glibc x64 |
| `bin/windows-x64/` | Windows x64 |

---

## 步骤 1: 拷贝 deploy/ 到目标机器

把整个 `deploy/` 文件夹拷贝到目标机器（U 盘 / scp / git clone 均可）。

```bash
# 方式: git clone (目标机器有 git)
git clone --depth 1 https://github.com/Hmbown/DeepSeek-TUI.git /tmp/ds-tui
cp -r /tmp/ds-tui/deploy ~/deepseek-deploy
rm -rf /tmp/ds-tui
```

以下假设部署目录为 `~/deepseek-deploy`（macOS/Linux）或 `C:\Users\用户名\deepseek-deploy`（Windows）。

---

## 步骤 2: 安装二进制

**已内置，跳过。** `deploy/bin/<平台>/` 下的二进制会被安装脚本自动拷贝到系统路径。

### 备用方案: 手动下载（仅当架构不匹配、需联网时）

<details>
<summary>展开</summary>

```bash
# macOS / Linux
npm install -g deepseek-tui

# 或从 GitHub Releases 下载:
# https://github.com/Hmbown/DeepSeek-TUI/releases
```
</details>

---

## 步骤 3: 配置 API Key

**macOS / Linux:**
```bash
deepseek auth set --provider deepseek
deepseek doctor           # 验证
```

**Windows:**
安装脚本运行时会提示输入 API Key，自动写入 `%USERPROFILE%\.deepseek\config.toml`。

---

## 步骤 4: 运行安装脚本

### macOS / Linux

```bash
cd ~/deepseek-deploy
./install-service.sh                  # 仅 API 服务
./install-service.sh --with-bridge    # API + 考试桥接
```

脚本自动: 检测 OS → 从 `bin/<平台>/` 装二进制 → 创建日志目录 → 生成 launchd / systemd 服务 → 启动 → 健康检查。

### Windows (x64)

以管理员身份打开 PowerShell:

```powershell
cd C:\Users\你的用户名\deepseek-deploy
powershell -ExecutionPolicy Bypass -File .\install-service.ps1
powershell -ExecutionPolicy Bypass -File .\install-service.ps1 -WithBridge
```

脚本自动: 检查管理员权限 → 装二进制到 `C:\Program Files\DeepSeek\` → 添加到系统 PATH → 提示输入 API Key → 用 sc.exe 创建 Windows 服务 → 启动 → 健康检查。

---

## 步骤 5: 验证服务

**所有平台:**
```bash
curl http://127.0.0.1:7878/health              # API 引擎
curl http://127.0.0.1:8888/health              # 考试桥接（如安装）
```

**功能测试（发送模拟试卷）:**
```bash
curl -X POST http://127.0.0.1:8888/exam/process \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "bridge-secret-change-me",
    "paper": "题目：1+1等于几？\n学生答案：2",
    "instruction": "请批改这道数学题，判断对错。",
    "model": "deepseek-v4-flash"
  }'
```

---

## 服务管理速查

| 操作 | macOS | Linux | Windows |
|------|-------|-------|---------|
| 查看状态 | `launchctl list \| grep deepseek` | `systemctl status deepseek-api` | `sc.exe query DeepSeekAPI` |
| 停止 | `launchctl unload ~/Library/LaunchAgents/com.deepseek.api.plist` | `sudo systemctl stop deepseek-api` | `sc.exe stop DeepSeekAPI` |
| 启动 | `launchctl load ~/Library/LaunchAgents/com.deepseek.api.plist` | `sudo systemctl start deepseek-api` | `sc.exe start DeepSeekAPI` |
| 重启 | unload → load | `sudo systemctl restart deepseek-api` | `sc.exe stop DeepSeekAPI && sc start` |
| API 日志 | `tail -f /usr/local/var/log/deepseek-api.log` | `journalctl -u deepseek-api -f` | 事件查看器 → 应用程序 |
| 桥接日志 | `tail -f /usr/local/var/log/exam-bridge.log` | `journalctl -u exam-bridge -f` | 事件查看器 → 应用程序 |

---

## 常见问题

### API 启动后 health 失败

```bash
# macOS / Linux: 看错误日志
tail -20 /usr/local/var/log/deepseek-api.err

# 手动试跑排查
deepseek serve --http --host 127.0.0.1 --port 7878
```

**Windows**: 打开事件查看器 → Windows 日志 → 应用程序，找 `DeepSeekAPI` 来源。

### 考试桥接报 python3 not found

**Windows**: 从 https://python.org 下载安装 Python 3（勾选 "Add to PATH"）。

### deepseek-tui 找不到

`deepseek serve --http` 依赖两个二进制 `deepseek` + `deepseek-tui`。安装脚本会自动处理，如果手动安装需确保两者在同一目录。

### 如何更新版本

替换 `deploy/bin/<平台>/` 下的二进制为新版本，重新运行安装脚本即可。

---

## 安装完成检查清单

- [ ] `deepseek --version` / `deepseek.exe --version` 输出版本号
- [ ] `curl http://127.0.0.1:7878/health` 返回 200
- [ ] 服务已设为开机自启
- [ ] (可选) `curl http://127.0.0.1:8888/health` 返回 ok
- [ ] (可选) 发送模拟试卷到 `/exam/process`，收到正确响应
