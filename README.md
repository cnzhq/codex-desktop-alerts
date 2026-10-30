# Codex Desktop Alerts

给 Windows 上的本地 Codex 增加跨对话的桌面提醒。任务执行期间可以切到其他窗口；本轮结束、请求操作批准或发出可识别的提问时，显示一个需要手动关闭的提示窗口。

**状态：`0.1.0a1`，源码安装的个人工具预览版。尚未在 GitHub 发布，采用 MIT 许可证。**

这是独立的 Python 辅助程序，不是 OpenAI 官方产品，也不是 VS Code 扩展。不需要 API Key，不调用模型，不修改 Codex 插件文件或审批规则。

## 功能和边界

| 项目 | 当前行为 |
| --- | --- |
| 跨对话 | 用户级 Hook；已有、新建、恢复的本机会话均在范围内 |
| 完成 | Hook 与会话文件新增记录双通路；表示本轮结束，不保证整个目标成功完成 |
| 审批 | `PermissionRequest` 事件；只提醒，不自动批准或拒绝 |
| 提问 | 匹配 `request_user_input`、`requestUserInput`、`elicitation` 工具名；不保证捕捉所有等待输入的路径 |
| 显示 | 独立 Tkinter 置顶窗口，保留到手动关闭；声音仅作辅助 |
| 多条提醒 | 按时间排队，显示项目名与对话短编号；未读提醒保留在磁盘，可在重启后重新显示 |
| 登录启动 | 普通用户 Startup 快捷方式，可选关闭；不是 Windows 服务或崩溃后自动重启服务 |
| 平台 | Windows 本地；暂不支持 WSL、SSH 远程主机、云任务、macOS、Linux 桌面 |
| 窗口定位 | 尝试回到一个现有 VS Code 窗口；不保证定位到对应对话或多窗口中的正确窗口 |

## 安装前准备

- Windows 桌面环境。
- Python **3.11 或以上**，带 Tcl/Tk 和 `pythonw.exe`。本项目无第三方 Python 运行依赖，不自动下载依赖。
- 使用支持生命周期 Hooks 的 Codex，并允许用户级 Hooks。已核对的本机版本为 `codex-cli 0.164.0-alpha.11.1`；这不是最低版本承诺。
- 能在 Codex 中使用 `/hooks` 审阅并信任脚本。信任由用户完成，安装器不写入信任记录，也不使用信任绕过参数。

下载仓库 ZIP 并解压，或克隆仓库。以下命令在项目目录的 PowerShell 中运行，无需管理员权限。

```powershell
# 先看计划：不会写文件、改配置、创建快捷方式或启动进程。
.\install.ps1 -Preview

# 确认计划后安装。
.\install.ps1
```

若 PowerShell 的执行策略阻止脚本，请先审阅来源和脚本内容，按照你所在环境的脚本策略处理；安装器不会调整执行策略。如果自动发现的 Python 不合适，可用 `-PythonExe 'C:\Path\To\python.exe'` 指定。

安装器默认将程序复制到 `%LOCALAPPDATA%\CodexDesktopAlerts`，合并 `%USERPROFILE%\.codex\hooks.json`，创建两个桌面入口和一个登录启动入口。如果设置了 `CODEX_HOME`，默认使用该目录。原 `hooks.json` 会先备份；`config.toml` 和 `notify` 保持原样。

**安装后还需要：**

1. 在 Codex 的 `/hooks` 界面核对三个 `Codex Desktop Alerts [v1]` 条目，检查命令确实指向刚才的安装目录，再信任它们。
2. 在 VS Code 执行 `Ctrl+Shift+P` → **开发人员: 重新加载窗口**。
3. 打开桌面 **Test Codex Alerts**，确认弹窗可见。
4. 按[真实验收步骤](docs/acceptance.md)分别测试已有 A 对话、另一个 B 对话和新建 C 对话；系统提示和模拟事件通过不能代替这一步。

若 IDE 中没有 Hook 审阅入口，可以在已安装、可交互使用的 Codex CLI 中输入 `/hooks`。不要把它当成一条要求模型“帮忙配置 hooks”的自然语言任务。CLI 与 IDE 必须使用同一个 `CODEX_HOME`。

## 常用操作

```powershell
# 检查后台心跳和监听状态。
py -3 "$env:LOCALAPPDATA\CodexDesktopAlerts\alerts.py" --status

# 发出测试提醒 / 打开提醒中心。
py -3 "$env:LOCALAPPDATA\CodexDesktopAlerts\alerts.py" --test
py -3 "$env:LOCALAPPDATA\CodexDesktopAlerts\alerts.py" --panel

# 暂停：当前登录期间，Hook 不会把后台程序重新启动。
py -3 "$env:LOCALAPPDATA\CodexDesktopAlerts\alerts.py" --stop
```

桌面的 **Codex Alerts** 可重新启动并打开提醒中心。下次登录也会重新启动（若安装时启用了登录启动）。“知道了”只处理一条，“全部已读”处理当前队列；关闭窗口不等于退出监听。

安装选项：

```powershell
.\install.ps1 -NoAutoStart                 # 不保留登录启动快捷方式
.\install.ps1 -NoShortcuts -NoStart       # 仅安装文件和 Hook，暂不启动
.\install.ps1 -CodexHome 'D:\CodexHome' -InstallDir 'D:\My Apps\CodexAlerts'
```

自定义安装目录由本地安装清单记录。自定义目录请使用其中的 `alerts.py` 操作。相同目录重复安装不会重复追加本工具的 Hook；更改 CodexHome 前应先停用旧环境。路径可包含空格和中文，但暂拒绝部分 Shell 特殊字符，避免命令转义含糊。

## 升级和停用

升级：下载新源码，再运行相同参数的 `install.ps1`。程序会先停止旧实例，保留提醒记录和配置备份。Hook 定义改变时，需要再次审阅信任并重载 VS Code。

```powershell
& "$env:LOCALAPPDATA\CodexDesktopAlerts\uninstall.ps1"
```

停用脚本只移除精确匹配本工具的 Hook 处理器和已记录的快捷方式，保留同组的其他处理器。它不删除程序、历史或配置备份，方便检查和恢复。旧 VS Code 进程中缓存的 Hook 会因 `disabled` 标记而停止发出提醒；重载窗口后卸载缓存。确认后可自行删除安装目录。

早期个人版本迁移与限制见[排错说明](docs/troubleshooting.md)。

## 实现方式与隐私

```text
用户级 Stop / PermissionRequest / PreToolUse Hook ─┐
                                                  ├─ 本地文件队列 → Python 后台程序 → 持久弹窗
所有日期的本机会话 JSONL 新增结束/提问记录 ────────┘
```

后台每秒检查文件变化，约每三秒发现新会话文件。启动时跳过既有会话正文，不回放所有历史；已经入队但尚未读的提醒会保留。Hook 和记录通路按事件标识去重。

会话文件不是稳定的公开接口，Codex 升级可能使补充监听失效。后台只能提醒它实际收到或识别到的事件，无法保证发现进程突然退出、断电、网络请求无限等待等情况。

不读取 `auth.json`，不访问网络，不上传数据。提醒程序读取会话文件的新增部分以识别事件，不把正文复制到提醒记录。运行数据包含项目路径、会话和轮次编号、事件类型、时间，仍属于个人本地数据。请勿将整个安装目录上传。详见[架构和数据流](docs/architecture.md)。

## 开发与发布

```powershell
py -3 -m unittest discover -s tests -v
.\tests\integration.ps1
py -3 scripts\build_release.py
```

单元测试不调用模型、真实 Hook、桌面弹窗或用户 Codex 配置；安装集成测试使用隔离的临时目录，不创建快捷方式、不启动后台。CI 配置包含 Windows Python 3.11/3.13/3.14，但远程 CI 尚未运行。

发布脚本按明确的源码清单生成 ZIP 和 SHA-256，不把用户配置、记录、缓存或 Git 元数据打包。完整流程见[发布准备](docs/releasing.md)、[贡献说明](CONTRIBUTING.md)和[变更记录](CHANGELOG.md)。

## 验证状态

本次实际执行结果见[本地验证记录](docs/validation.md)。

- 个人原型：用户已确认测试弹窗可见，全局 Hook 已核查为受信任。
- 本项目：应以实际测试输出为准；自动化覆盖记录解析、跨对话模拟、队列恢复、去重、配置保留和隔离安装/停用。
- 发布门槛：在 VS Code 重载后完成真实 A/B/C 对话和审批/提问验收，并记录系统、Python、Codex 版本。尚未完成，不应宣称所有场景已验证。

## 许可证与来源

本项目采用 [MIT 许可证](LICENSE)。版权声明使用项目贡献者名称：Codex Desktop Alerts contributors。

Hook 机制、信任要求和事件定义参考 [OpenAI 官方 Hooks 文档](https://learn.chatgpt.com/docs/hooks)。本项目中的会话 JSONL 解析器来自本地格式观察，兼容性范围与官方 Hook API 不同。
