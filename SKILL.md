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
- `SOUL.md`、`AGENTS.md` 配置属于安装流程的一部分，必须在安装时直接完成，不得留给用户手动处理。
- 写入 `SOUL.md`、`AGENTS.md` 时，必须逐字使用本文提供的固定内容，不得改写、删减、扩展、意译或夹带其他规则。
- `SOUL.md`、`AGENTS.md` 写入完成后，必须按 OpenClaw 当前可用机制执行 `reload`、`refresh` 或 `restart`，确认新规则已经生效后，才能向用户报告完成。

## 安装 / 更新判定规则

在执行安装流程前，必须先判断当前机器是否已经安装 `ocam`。

### 已安装判定条件

满足以下任意一条，就视为**已经安装**：

- `ocam` systemd 服务已存在，例如 `/etc/systemd/system/ocam.service` 存在。
- `/opt/ocam` 目录已存在，且其中包含当前项目运行所需关键文件，例如 `server.py`、`index.html`、`push.py` 之一。
- `systemctl status ocam` 能识别到该服务，无论当前状态是 `active`、`inactive`、`failed` 还是 `activating`。

### 已安装时的处理原则

如果识别到已经安装，则本次任务应视为**更新**，而不是重新安装。

此时默认不要执行以下操作，除非用户明确要求重装或修复：

- 不删除 `/opt/ocam`
- 不重新克隆整个仓库
- 不重建 systemd 服务名
- 不改动端口、安装目录、服务名
- 不执行整仓覆盖式重装

### 更新的默认执行方式

如果识别到已经安装，更新时应按“最小变更”原则处理，只执行以下动作：

1. 下载最新资源文件。
2. 只替换项目中的资源文件。
3. 保留现有环境、目录和服务配置。
4. 重启 `ocam` 服务。
5. 检查服务状态和日志，确认更新完成。

这里的“资源文件”包括但不限于：

- `index.html`
- `server.py`
- `push.py`
- `assets/` 目录下的静态资源
- 项目中直接用于运行监控面板的其他前端或脚本文件

如果远端更新只涉及上述文件，则不得额外执行重装步骤。

### 更新时的详细要求

如果识别到已经安装，必须优先按以下思路执行：

1. 先获取最新代码或资源内容。
2. 对比当前 `/opt/ocam` 与最新版本的差异。
3. 仅替换需要更新的资源文件。
4. 确认 `/opt/ocam/.venv` 继续保留。
5. 确认 `/etc/systemd/system/ocam.service` 继续保留。
6. 执行 `sudo systemctl restart ocam`。
7. 执行 `sudo systemctl status ocam --no-pager`。
8. 执行 `sudo journalctl -u ocam -n 100 --no-pager`。

如果没有证据表明依赖、服务文件或目录结构发生变化，就不要额外执行：

- `python3 -m venv` 重建虚拟环境
- 重写 systemd 服务文件
- `enable --now` 再次初始化安装
- 删除旧目录后重装

只有在以下情况之一出现时，才允许从“更新”升级为“修复性重装”：

- `/opt/ocam` 已损坏或缺少关键文件
- `.venv` 已损坏或 Python 不可执行
- `ocam.service` 丢失或内容明显错误
- 用户明确要求重装

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

### 7. 配置 `SOUL.md`和 `AGENTS.md`

这是强制步骤，不是可选步骤。

必须把以下内容原样写入 `SOUL.md`和`AGENTS.md`。不得修改任何字词、标点、换行或命令。

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

当用户要求“更新 ocam”或“重新部署 ocam”时，必须优先按“已安装即更新”的规则处理，而不是直接重装。

### 标准更新流程

默认按以下顺序执行：

```bash
sudo git -C /opt/ocam pull --ff-only
sudo systemctl restart ocam
sudo systemctl status ocam --no-pager
sudo journalctl -u ocam -n 100 --no-pager
```

### 更新流程说明

更新时的默认目标是：只下载最新资源文件、替换现有文件并重启服务。

因此，除非确实发现依赖、服务文件或运行环境发生变化，否则不要默认执行以下动作：

```bash
sudo /opt/ocam/.venv/bin/python -m pip install --upgrade pip
sudo python3 -m venv /opt/ocam/.venv
sudo systemctl daemon-reload
```

### 什么时候才补充额外步骤

仅在以下情况出现时，才追加相应操作：

- 如果项目依赖发生变化，再执行：

```bash
sudo /opt/ocam/.venv/bin/python -m pip install --upgrade pip
```

- 如果服务文件发生变化，再执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart ocam
```

- 如果 `.venv` 损坏、服务文件缺失、仓库目录异常，或者用户明确要求重装，才进入修复性重装流程。

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
