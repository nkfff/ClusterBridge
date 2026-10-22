# ClusterBridge

轻量级 SSH 数据中转桌面应用：电脑同时连接源端和目标端，按块读取并写入数据，不把完整文件落到本地磁盘。

## MVP 范围

- 集群 ↔ 集群、集群 ↔ 本地目录的单文件流式传输
- SSH 配置保存在本地 SQLite；密码只交给操作系统钥匙串（`keyring`）
- SSH 主机密钥默认由 AsyncSSH 校验，不提供“忽略主机密钥”选项
- 可配置 4 MiB 内存缓冲
- 目标端已有文件时按文件大小续传；源文件变更会拒绝续传
- 任务取消、进度回调和失败信息

当前 MVP 保持单任务、单文件传输。递归目录、并发小文件、ProxyJump、分段校验和系统休眠抑制属于后续版本，避免在核心传输可靠性验证前扩大范围。

## 运行

需要 Python 3.11+：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m clusterbridge
```

首次运行时，应用会创建 `~/.clusterbridge/clusterbridge.sqlite3`。数据库只保存连接元数据，不保存密码；密码通过钥匙串条目 `clusterbridge/<connection-id>` 保存。

## 传输模型

```
source SFTP/local file -> bounded asyncio queue -> destination SFTP/local file
```

缓冲队列有固定容量，生产者和消费者通过背压协作，因此本地内存占用与文件大小无关。源端和目标端连接都在任务结束或取消时关闭。

## 安全边界

- 不支持把密码写入 SQLite、日志或任务历史。
- 首次连接要求用户确认/接受正确的 SSH 主机指纹；不要为了“方便”关闭校验。
- 连接名称、地址和路径仍属于敏感元数据，建议只在个人账户下使用默认数据库权限。
- 中转数据会经过本机网络栈和内存；使用前确认符合集群和科研数据管理规定。

## 项目结构

- `clusterbridge/models.py`：连接与传输任务数据模型
- `clusterbridge/storage.py`：SQLite 元数据存储
- `clusterbridge/secrets.py`：系统钥匙串适配
- `clusterbridge/transfer.py`：受背压控制的本地/SSH 流式传输
- `clusterbridge/ui.py`：PySide6 单窗口 MVP

## 后续路线

1. 目录递归清单与逐文件断点续传
2. 分段哈希校验、源文件快照和安全覆盖策略
3. 并发小文件队列与带宽限制
4. ProxyJump、连接测试、系统休眠抑制
5. PyInstaller 打包和 macOS/Windows/Linux 发布测试
