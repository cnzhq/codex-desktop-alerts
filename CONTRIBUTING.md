# 贡献与维护

当前版本处于个人项目的发布准备阶段，采用 MIT 许可证。请在提交贡献前阅读 LICENSE，并确认你有权提供相应内容。

## 本地开发

使用 Python 3.11+。核心逻辑只有标准库依赖；Windows GUI 使用 Tkinter 和 ctypes。

```powershell
python -m unittest discover -s tests -v
python -m compileall -q alerts.py hook_config.py manage.py scripts tests
.\tests\integration.ps1
# Optional: creates a short-lived popup in an isolated installation; run in a desktop session.
.\tests\gui_smoke.ps1
python scripts\build_release.py
```

集成测试只使用临时目录，保留测试产物供检查。不要在测试中使用真实用户凭据、真实会话正文或默认 Codex 配置。

## 改动原则

- 通知错误不能改变审批结果、阻止正常操作或自动向模型发送消息。
- 不修改官方插件安装文件，不依赖某个固定对话 ID。
- 更新 Hook 时保留其他事件、组元数据和同组处理器；测试重复安装与停用。
- 新的会话格式必须有脱敏合成 fixture 和回归测试，并记录已验证版本。
- 所有运行记录、配置备份和本地路径留在运行目录。提交前检查 diff 与发布 ZIP。
- 自动测试不能替代真实多对话、桌面和审批/提问验收；PR 中区分已执行和待执行项目。

## 提交说明

说明问题触发条件、改动后的行为、验证命令和结果。若影响已安装 Hook 的定义，注明需要重新审阅信任。若涉及文件读取或命令调用，解释数据范围与命令参数的构造方式。
