# Kabuqina — Release checklist（Windows NSIS）

面向 **NSIS / `cargo tauri build`** 的发布前自检。前置要求与工作流概要见仓库根目录 [AGENTS.md](../AGENTS.md)。

---

## 1. 环境与仓库

- [ ] **PowerShell 7+**，**Node 20+**，**Rust 1.80+**
- [ ] 若在 release 构建中遇到 ** MSVC / 原生 wheel** 问题：使用 **Developer PowerShell for VS** 或已配置 VC 的环境（见 [embedded-python-bundled.md](embedded-python-bundled.md)）
- [ ] `git status` 干净；准备打的 **标签 / 版本号** 与配置一致（见第 2 节）

---

## 2. 版本与标识

- [ ] [tauri/tauri.conf.json](../tauri/tauri.conf.json)：根级 `version`
- [ ] [tauri/Cargo.toml](../tauri/Cargo.toml)：`package.version`（与上面对齐）
- [ ] [web/package.json](../web/package.json)、[web/package-lock.json](../web/package-lock.json) 版本一致；运行 `scripts/check_release.ps1 -ExpectedVersion vX.Y.Z`
- [ ] [docs/releases](releases/) 下存在与 tag 同名的 `vX.Y.Z.md` Release Note；官方产物由 owner 应用私有 Tier 2 品牌 overlay 后在本机构建，tag 不自动构建公开仓库中的无品牌 placeholder 版本
- [ ] `identifier`：**`com.kabuqina.app`** — 不要随意修改；与用户数据 `%LOCALAPPDATA%\com.kabuqina.app\` 绑定
- [ ] **`productName`**：保持 **ASCII**（如 `Kabuqina`），否则 WiX `light.exe` 可能无法生成 `.msi`（中文输出路径会失败）
- [ ] **快捷方式 /「应用和功能」中文名**：由 [tauri/wix/main.wxs](../tauri/wix/main.wxs) 自定义模板设置（如 **卡布奇娜**）；改显示名时改该模板，不要改 `productName` 为中文
- [ ] **`app.windows[].title`**：主窗口标题，与对产品名的期望一致
- [ ] 若需固定的 **英文字符 exe 文件名**：使用「顶层」的 **`mainBinaryName`**（见 [Tauri — Config `mainBinaryName`](https://v2.tauri.app/reference/config/)）；不要单靠改 Cargo 程序名凑合

---

## 3. 构建顺序（请勿打乱）

仓库约定顺序：[AGENTS.md](../AGENTS.md)「构建流程」一节。

1. [ ] **`.\scripts\apply-brand-overlay.ps1 -Apply`**（官方发行版；`KABUQINA_BRAND_DIR` 指向私有品牌仓库；真实资产只进入工作树，绝不提交）
2. [ ] **`.\python\build_bundle.ps1 -Verify`**（canonical Kabuqina runtime；不含上游 SPA）
3. [ ] **`cd web` → `npm ci` → `npm run build`**
4. [ ] **`cd tauri` → `cargo tauri build`**（`bundle.targets` 含 **nsis**；完整 bundle ~2GB 超出 WiX MSI 单 cab 上限，故用 NSIS）
5. [ ] 保存产物后运行 **`.\scripts\apply-brand-overlay.ps1 -Restore`** 和 **`-Check`**，确认真实品牌资产未留在待提交工作树

---

## 4. NSIS 产物与品牌化

- [ ] **输出路径**：`tauri/target/release/bundle/nsis/` 下 `*-setup.exe` 文件名、架构符合预期
- [ ] **品牌名注意**：NSIS 使用 `productName`（ASCII `Kabuqina`）作为「应用和功能」/快捷方式名；WiX 模板 [tauri/wix/main.wxs](../tauri/wix/main.wxs) 的中文显示名（卡布奇娜）**不再生效**（NSIS 不读 WiX 模板）。如需安装器中文名，后续在 `bundle.windows.nsis` 配置
- [ ] **`publisher` / `copyright` / `shortDescription` / `longDescription`** 是否与当前对外文案一致（摘要会出现在「应用和功能」等处）
- [ ] **已安装过一次**的机器上更换 `productName` 后：**旧桌面 `.lnk`** 可能不会自动更名；卸载重装或删除旧快捷方式再验证

---

## 5. 代码签名（若适用）

详见 [code-signing.md](code-signing.md)。

- [ ] `certificateThumbprint`、`digestAlgorithm`、`timestampUrl` 已配置
- [ ] 构建产物 **`Get-AuthenticodeSignature`**（或 CI 等价步骤）通过

---

## 6. 安装后冒烟

### 6.1 首次启动 / onboarding

Splash 路由逻辑见 `web/src/Splash.tsx`：有密钥或允许「稍后配置」会跳过 onboarding。

- [ ] 需要 **强制 onboarding**：关闭应用后删除 **`%LOCALAPPDATA%\com.kabuqina.app\`**，并在 Windows **凭证管理器** 中删除服务名为 **Kabuqina** 的条目（细节见仓库内 onboarding / 密钥相关代码与 FAQ）
- [ ] **Splash → onboarding** → 完成向导或按需进入 `/chat`

### 6.2 日常使用路径

- [ ] LLM：**保存密钥**后能正常进入 **`/chat`**；Python web 子进程无启动失败（日志在 `%LOCALAPPDATA%\com.kabuqina.app\`）
- [ ] 本次版本改动涉及到的 **Settings / Gateway / 配对** 等分支手动点一遍

### 6.3 环境与网络

- [ ] **系统代理**：Clash / MITM / 公司代理不误伤 **loopback**（见 [troubleshooting.md](troubleshooting.md) § loopback）

### 6.4 卸载 / 升级

- [ ] 「应用和功能」**卸载** 成功；**重装**后应用可启动
- [ ] 若面向老用户：**从上一版升级**（覆盖安装），快捷方式与数据目录行为符合预期

### 6.5 Study notebook / D-5

- [ ] 使用一次性 owner/fixture；破坏性测试前已导出可恢复备份，未使用真实学习数据
- [ ] `/study` 五个生命周期页面、两个课程隔离、deep link、草稿治理、错题重试与练习在
  **release WebView2 bundle** 中通过（不能用 Vite dev 代替）
- [ ] 窄/中/宽、亮/暗、中英、纯键盘、200% 缩放、reduced motion、offline 与 desk child
  restart 组合轮通过
- [ ] 学习功能改进计数默认关闭；开启后只有批准的 enum/coarse count，关闭后本机 aggregate
  被清除；fixture title/question/answer/id/source_refs/URL 不出现在序列化事件或产物中
- [ ] **D-5 accepted degradation 核对**：v0.4 未执行 pre-D5 profile/flashcard/quiz 的
  installed-NSIS 旧样本升级专测，不得在 Release Note/测试报告中写成已通过；确认隔离
  one-shot adapters、失败保留旧 key、migration diagnostics/failure export 仍在产物中
- [ ] 后续若要删除任一 legacy Study reader/adapter，必须先补真实旧 app-data 的
  成功/失败/重启/幂等，以及与 A-R3 persistence migration 同时发生的 installed 升级证据

---

## 7. Shell 与 desk API

- [ ] Web shell 的 `/chat`、Settings 与 sessions 均能通过随机 loopback 端口访问 desk API；控制台无 CSP / 连接类报错

---

## 8. 发布物与对外说明

- [ ] **GitHub Draft Release**：从 owner 本机官方品牌构建附上 **`*-setup.exe`**；完成安装冒烟和覆盖安装测试后再 Publish
- [ ] **手工覆盖安装**：若面向旧版 Windows 用户，Release Note 给出下载安装包的方式，并验证覆盖安装保留 app data
- [ ] **校验和 / 签名说明**写入 Release Note（按需）
- [ ] [README.md](../README.md) 或其它对外文档若写死 NSIS 文件名，与当前 `productName` / 架构后缀一致

---

## 9. 省时排障提示

- [ ] Python 运行时 / gateway **行为怪异**且日志提示 bundle 陈旧：先做 **`python/build_bundle.ps1`** 再打 MSI，而非只重复 `cargo tauri build`
- [ ] **`webviewInstallMode`**：确认目标机 WebView2 安装体验可接受（见 [tauri/tauri.conf.json](../tauri/tauri.conf.json)）

---

修订此清单时：**只增加可操作的勾选项**；泛泛的「再多测测」不写进表格。
