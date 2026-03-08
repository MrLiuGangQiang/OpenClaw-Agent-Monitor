---
name: ocam-auto-install
description: Install, update, enable, start, restart, and troubleshoot OpenClaw Agent Monitor as a Linux systemd service named `ocam` under `/opt/ocam`. Use when OpenClaw needs to deploy this project from `https://github.com/MrLiuGangQiang/OpenClaw-Agent-Monitor`, configure boot auto-start, repair the service, or verify that the dashboard is running.
---

# OCAM Auto Install Skill

使用这个 Skill 时，默认目标固定如下：

- 服务名：`ocam`
- 安装目录：`/opt/ocam`
- 仓库地址：`https://github.com/MrLiuGangQiang/OpenClaw-Agent-Monitor`
- HTTP 端口：`7654`
- WebSocket 端口：`7655`
- 进程管理：`systemd`

你的任务是：尽量少问问题，直接完成安装、开机自启、启动验证、`SOUL.md` 配置和规则生效确认。

## 强制规则

- 默认目标机器是带 `systemd` 的 Linux，优先按 Ubuntu / Debian 方式执行。
- 涉及 `/opt`、`/etc/systemd/system`、`systemctl` 时，必须先请求提权。
- 除非用户明确要求，否则不得修改服务名、安装路径、端口。
- 不得使用 `nohup`、`screen`、`tmux` 代替 `systemd`。
- 不得把服务跑在临时 shell 中后直接结束；必须完成 `enable --now`。
- 不创建专用系统用户。
- `SOUL.md` 配置属于安装流程的一部分，必须在安装时直接完成，不得留给用户手动处理。
- 写入 `SOUL.md` 时，必须逐字使用本文提供的固定内容，不得改写、删减、扩展、意译或夹带其他规则。
- `SOUL.md` 写入完成后，必须按 OpenClaw 当前可用机制执行 `reload`、`refresh` 或 `restart`，确认新规则已经生效后，才能向用户报告完成。

## 安装流程

必须按以下顺序执行。

### 1. 安装系统依赖

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv
```

如果目标机器不是 Debian / Ubuntu，改用对应包管理器安装等价依赖，但服务名、安装目录和端口仍保持不变。

### 2. 安装或更新项目到 `/opt/ocam`

如果 `/opt/ocam` 已存在且是正确的 Git 仓库，就直接更新；否则重新克隆。

```bash
if [ -d /opt/ocam/.git ]; then
  sudo git -C /opt/ocam pull --ff-only
else
  sudo rm -rf /opt/ocam
  sudo git clone https://github.com/MrLiuGangQiang/OpenClaw-Agent-Monitor /opt/ocam
fi
```

### 3. 创建 Python 虚拟环境

当前项目默认没有 `/opt/ocam/requirements.txt`。这里不要检查 `requirements.txt`，只创建虚拟环境并升级 `pip`。

```bash
sudo python3 -m venv /opt/ocam/.venv
sudo /opt/ocam/.venv/bin/python -m pip install --upgrade pip
```

### 4. 确认目录权限

不创建专用用户，因此这里只确认 `/opt/ocam` 的现有权限足以让 `systemd` 正常读取并执行项目文件。

### 5. 写入 systemd 服务

必须创建 `/etc/systemd/system/ocam.service`，内容如下：

```ini
[Unit]
Description=OpenClaw Agent Monitor (ocam)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/ocam
Environment=OPENCLAW_AGENT_BOARD_HOST=0.0.0.0
Environment=OPENCLAW_AGENT_BOARD_PORT=7654
Environment=OPENCLAW_AGENT_BOARD_WS_PORT=7655
ExecStart=/opt/ocam/.venv/bin/python /opt/ocam/server.py
Restart=always
RestartSec=2
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

推荐直接执行：

```bash
sudo tee /etc/systemd/system/ocam.service >/dev/null <<'EOF'
[Unit]
Description=OpenClaw Agent Monitor (ocam)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/ocam
Environment=OPENCLAW_AGENT_BOARD_HOST=0.0.0.0
Environment=OPENCLAW_AGENT_BOARD_PORT=7654
Environment=OPENCLAW_AGENT_BOARD_WS_PORT=7655
ExecStart=/opt/ocam/.venv/bin/python /opt/ocam/server.py
Restart=always
RestartSec=2
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
```

### 6. 设置开机自启并立即启动

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ocam
sudo systemctl --no-pager --full status ocam
```

### 7. 配置 `SOUL.md`

这是强制步骤，不是可选步骤。

必须把以下内容原样写入 `SOUL.md`。不得修改任何字词、标点、换行或命令。

```md
## OCAM

- On every task, before doing anything else, you MUST first run: `python3 /opt/ocam/push.py <state> "<description>" --agent-id <current_agent_id>`.
- This is mandatory for every task, with no skipping, no batching, and no exceptions unless the command is unavailable or explicitly prohibited.
- You must treat the OCAM push as a first step of task execution, not an optional status update.
- After finishing the task, you MUST run: `python3 /opt/ocam/push.py idle "等待任务..." --agent-id <current_agent_id>` before replying to the user.
- If you realize you missed the pre-task OCAM push, you must acknowledge it plainly and correct your behavior on subsequent tasks.
```

### 8. 让 OpenClaw 读取新规则

`SOUL.md` 写入完成后，不得只写文件不生效。必须立即按 OpenClaw 当前可用机制执行 `reload`、`refresh` 或 `restart`，并确认新规则已经被读取。

## 安装后必须验证

至少完成以下验证。

### 1. 查看服务状态

```bash
sudo systemctl status ocam --no-pager
```

### 2. 查看最近日志

```bash
sudo journalctl -u ocam -n 100 --no-pager
```

### 3. 查看 HTTP 接口

```bash
curl http://127.0.0.1:7654/api/agents
```

### 4. 告诉用户访问地址

默认访问地址：

```text
http://127.0.0.1:7654
```

如果用户需要局域网访问，再告诉用户使用该机器的实际 IP 加端口 `7654`。

## 更新流程

当用户要求“更新 ocam”或“重新部署 ocam”时，必须执行：

```bash
sudo git -C /opt/ocam pull --ff-only
sudo /opt/ocam/.venv/bin/python -m pip install --upgrade pip
sudo systemctl restart ocam
sudo systemctl status ocam --no-pager
```

如果服务文件发生变化，再补执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart ocam
```

## 常用运维命令

### 重启

```bash
sudo systemctl restart ocam
```

### 停止

```bash
sudo systemctl stop ocam
```

### 查看开机自启状态

```bash
sudo systemctl is-enabled ocam
```

### 查看实时日志

```bash
sudo journalctl -u ocam -f
```

## 故障排查

### 端口占用

如果 `7654` 或 `7655` 被占用，先查占用进程：

```bash
sudo ss -ltnp | grep -E ':7654|:7655'
```

如果必须改端口，只修改 systemd 服务中的以下环境变量：

- `OPENCLAW_AGENT_BOARD_PORT`
- `OPENCLAW_AGENT_BOARD_WS_PORT`

修改后必须执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart ocam
```

### 服务起不来

优先检查：

```bash
sudo systemctl status ocam --no-pager
sudo journalctl -u ocam -n 200 --no-pager
```

重点检查：

- `/opt/ocam/server.py` 是否存在
- `/opt/ocam/index.html` 是否存在
- `/opt/ocam/.venv/bin/python` 是否存在
- `/opt/ocam` 的权限是否允许当前 systemd 服务正常读取与执行

### 仓库目录异常

如果 `/opt/ocam` 不是正常 Git 仓库，直接按以下方式重装：

```bash
sudo systemctl stop ocam || true
sudo rm -rf /opt/ocam
sudo git clone https://github.com/MrLiuGangQiang/OpenClaw-Agent-Monitor /opt/ocam
sudo python3 -m venv /opt/ocam/.venv
sudo /opt/ocam/.venv/bin/python -m pip install --upgrade pip
sudo systemctl restart ocam
```

## 卸载流程

只有在用户明确要求卸载时才执行：

```bash
sudo systemctl disable --now ocam
sudo rm -f /etc/systemd/system/ocam.service
sudo systemctl daemon-reload
sudo rm -rf /opt/ocam
```

## 对用户的反馈模板

安装成功后，优先使用：

> `ocam` 已安装并设置为开机自启，默认访问地址是 `http://127.0.0.1:7654`。

更新成功后，优先使用：

> `ocam` 已更新并重启完成，服务当前正常运行。
