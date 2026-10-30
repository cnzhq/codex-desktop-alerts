# 发布准备与操作

## 当前状态

本地项目名称：codex-desktop-alerts；版本：0.1.0a1。尚未创建远程仓库、push、打 Git 标签或发布 GitHub Release。已按维护者决定添加 MIT 许可证。

## 发布前检查

- [ ] 维护者确定仓库所有者、公开/私有可见性和名称；核对 MIT 版权声明。
- [ ] 按 acceptance.md 执行真实 A/B/C、恢复旧会话、审批和结构化提问验收。
- [ ] 在干净 Windows 用户或第二台机器上验证安装、登录启动、升级和停用。
- [ ] 记录 Windows / Python / Codex 版本，区分本地自动测试和远程 CI。
- [ ] 检查 README 的验证状态，不宣称未执行的兼容性。
- [ ] 运行测试和源码包构建，检查 ZIP 文件列表及 SHA-256。
- [ ] 检查 git diff、暂存区和历史；没有用户名、机器名、会话、日志、配置备份或凭据。
- [ ] 若加入截图，只使用合成项目、合成对话标识，裁掉桌面和私人内容。
- [ ] 确认文档中的 Issue / 私密问题报告方式适合实际仓库设置。

## 本地生成分发包

```powershell
python -m unittest discover -s tests -v
.\tests\integration.ps1
python scripts\build_release.py
```

脚本输出 `dist/codex-desktop-alerts-0.1.0a1.zip` 与 `dist/SHA256SUMS.txt`。使用固定成员顺序、时间戳和文件权限；相同源文件应生成相同 SHA-256。它是源码 ZIP，不是签名 EXE。没有自动下载或捆绑 Python。

## GitHub 初次发布

以下步骤由维护者在确认后执行；示例不包含真实仓库地址或凭据。

1. 在 GitHub 创建选择好可见性的空仓库。不要把本机安装目录当作仓库来源。
2. 在本项目本地 Git 仓库检查状态。若尚未提交，用自己的 Git 身份提交审阅后的源码。
3. 将 remote 指向维护者刚创建的仓库，再 push main。
4. 等待 GitHub Actions 的 Windows 测试。仓库首次上传之前无法获得远程 CI 成功记录。
5. 检查完发布门槛后创建预发布标签与 Release，附源码 ZIP、校验文件和明确限制，并注明 MIT 许可证。

本仓库的 CI 仅测试并上传 Actions 构建产物，没有自动创建 Release 或向 GitHub 发内容的工作流。

## 发布说明草稿

> Windows 上用于本地 Codex 的跨对话桌面提醒工具预览版。支持本轮结束、操作审批和部分结构化提问事件。需 Python 3.11+ 与手动审阅 Hook。会话文件补充监听可能受 Codex 版本变化影响，不覆盖 WSL/SSH/云端模式。采用 MIT 许可证。具体测试范围请附本次实际验收记录。
