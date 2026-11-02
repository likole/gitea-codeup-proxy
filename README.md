# gitea-codeup-proxy

轻量级 HTTP 反向代理，专门用于解决 Gitea 向阿里云 Codeup 推送或拉取含 LFS 的仓库时报错的问题。

## 解决的问题

* **原因**：阿里云 Codeup 要求 Git LFS Batch 请求必须携带 `ref` 字段，而 Gitea 默认未提供该字段，导致推送 LFS 对象时报 HTTP 422 校验失败。
* **解决方案**：代理拦截 `/info/lfs/objects/batch` 请求，自动注入 `{"ref": {"name": "HEAD"}}` 后转发至 Codeup。

## 快速使用

### 1. 部署服务

将 `codeup_proxy.py` 放置于 `/opt/gitea/codeup_proxy.py`，并将 `codeup-lfs-proxy.service` 复制至 `/etc/systemd/system/`：

```bash
sudo cp codeup-lfs-proxy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now codeup-lfs-proxy.service
```

### 2. 配置 Gitea Push Mirror

在 Gitea 仓库的「仓库设置」->「镜像」->「推送镜像」中配置：

* **镜像地址**：
  ```text
  http://172.20.0.1:8899/<组织或用户名>/<仓库名>.git
  ```
  *(注：`172.20.0.1` 替换为 Gitea 容器访问宿主机代理服务的内网 IP)*
* **认证凭据**：填写阿里云 Codeup 的 HTTPS 克隆账号与个人访问令牌（Personal Access Token）。
