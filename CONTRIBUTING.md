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

## 提交规范：真人与 AI 一致适用

所有贡献者，包括维护者、其他真人贡献者以及 Codex、ChatGPT 等 AI 辅助工具，都必须使用 [Conventional Commits 1.0.0（约定式提交）](https://www.conventionalcommits.org/zh-hans/v1.0.0/)。生成提交消息、直接提交和合并时最终形成的提交消息均遵守此约定；AI 不享有例外。

基本格式：

```text
<type>[(scope)][!]: <简明描述>

[可选正文]

[可选脚注]
```

- 类型使用英文小写：`feat`（新功能）、`fix`（修复）、`docs`（文档）、`test`（测试）、`refactor`（不改变行为的重构）、`perf`（性能）、`build`（构建或依赖）、`ci`（持续集成）、`style`（纯格式）、`chore`（其他维护）。这是本项目采用的类型集合。
- scope 可选，使用有意义的模块名，例如 `hooks`、`queue`、`installer`、`release`。
- 使用英文半角冒号，冒号后保留一个空格。描述说明实际变化，推荐使用简体中文，避免“更新一下”“AI 修改”等模糊消息。
- 每条提交围绕一个清晰目的；无关改动应拆分。格式合规不能代替内容准确。
- 破坏兼容性的改动在类型/范围后加 `!`，并在正文后的 `BREAKING CHANGE:` 脚注解释影响与迁移方式。
- 非简单改动的正文说明问题触发条件、改动后的行为和验证结果；未执行的验证必须如实注明。若影响 Hook 定义，说明需要重新审阅信任；涉及文件读取或命令调用时说明数据范围与参数构造。

示例：

```text
feat(queue): 恢复重启前尚未确认的提醒
fix(installer): 卸载时保留同组的其他 Hook
docs: 补充安装步骤
```

### 共同作者与 AI 署名

共同作者脚注与约定式提交兼容。仅在对应贡献者确实参与本次改动时添加，不要把所有 AI 名称自动附到每条提交。由 Codex 实质参与的提交使用：

```text
docs: 明确提交规范与 AI 协作署名

统一真人与 AI 的提交要求，并说明项目协作分工。

Co-authored-by: Codex <codex@openai.com>
```

主作者仍使用实际提交者的 Git 身份；不要冒充其他真人、机构或其他 AI。其他共同作者应使用其可验证且适合公开的署名邮箱。是否显示头像及计入贡献者统计由 GitHub 关联与统计结果决定，不以提交中出现一个名字作为保证。

已发布的提交历史不为补署名而自动 amend 或 force push；只有获得维护者明确授权才可改写历史。优先在下一条实际参与的改动中署名，不创建仅用于增加贡献者计数的空提交。

提交前由贡献者自行核对消息；维护者在审阅和合并时同样检查。当前这是项目约定，尚未配置 commitlint、提交消息校验 Hook 或分支保护强制执行。
