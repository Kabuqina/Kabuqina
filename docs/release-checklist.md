# Kabuqina — Release checklist（Windows MSI）

面向 **MSI / `cargo tauri build`** 的发布前自检。前置要求与工作流概要见仓库根目录 [AGENTS.md](../AGENTS.md)。

---

## 1. 环境与仓库

- [ ] **PowerShell 7+**，**Node 20+**，**Rust 1.80+**
- [ ] 若在 release 构建中遇到 ** MSVC / 原生 wheel** 问题：使用 **Developer PowerShell for VS** 或已配置 VC 的环境（见 [embedded-python-bundled.md](embedded-python-bundled.md)）
- [ ] `git status` 干净；准备打的 **标签 / 版本号** 与配置一致（见第 2 节）

---

## 2. 版本与标识

- [ ] [tauri/tauri.conf.json](../tauri/tauri.conf.json)：根级 `version`
- [ ] [tauri/Cargo.toml](../tauri/Cargo.toml)：`package.version`（与上面对齐）
- [ ] `identifier`：**`com.kabuqina.app`** — 不要随意修改；与用户数据 `%LOCALAPPDATA%\com.kabuqina.app\` 绑定
- [ ] **`productName`**：保持 **ASCII**（如 `Kabuqina`），否则 WiX `light.exe` 可能无法生成 `.msi`（中文输出路径会失败）
- [ ] **快捷方式 /「应用和功能」中文名**：由 [tauri/wix/main.wxs](../tauri/wix/main.wxs) 自定义模板设置（如 **卡布奇娜**）；改显示名时改该模板，不要改 `productName` 为中文
- [ ] **`app.windows[].title`**：主窗口标题，与对产品名的期望一致
- [ ] 若需固定的 **英文字符 exe 文件名**：使用「顶层」的 **`mainBinaryName`**（见 [Tauri — Config `mainBinaryName`](https://v2.tauri.app/reference/config/)）；不要单靠改 Cargo 程序名凑合

---

## 3. 构建顺序（请勿打乱）

仓库约定顺序：[AGENTS.md](../AGENTS.md)「构建流程」一节。

1. [ ] **`.\python\build_bundle.ps1 -Verify`**（含 Hermes SPA、runtime）
2. [ ] **`cd web` → `npm ci` → `npm run build`**
3. [ ] **`cd tauri` → `cargo tauri build`**（`bundle.targets` 含 **msi**）

---

## 4. MSI 产物与品牌化

- [ ] **输出路径**：`tauri/target/release/bundle/msi/` 下文件名、架构、`en-US` / 其他 WiX language 后缀符合预期
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

---

## 7. Hermes shell 跳转

- [ ] Web shell 跳转至 **`http://127.0.0.1:<port>`** 的 Hermes dashboard 仍可打开；控制台无 CSP / 连接类报错

---

## 8. 发布物与对外说明

- [ ] **GitHub Release**：附上 **`.msi`**、**`.msi.zip`**、**`.msi.zip.sig`**、**`latest.json`**
- [ ] **腾讯 COS 备用源**：上传同版本 **`.msi.zip`**、**`.msi.zip.sig`**，并将 COS 版 manifest 上传为 **`latest.json`**
- [ ] **Updater key**：`tauri/tauri.conf.json#plugins.updater.pubkey` 与本次签名私钥匹配；私钥只存在于本机安全位置或 CI secret
- [ ] **Updater endpoint smoke**：发布前手动打开 GitHub `latest.json` 与 COS `latest.json`，确认两者版本一致、URL 可下载、signature 非空
- [ ] **校验和 / 签名说明**写入 Release Note（按需）
- [ ] [README.md](../README.md) 或其它对外文档若写死 MSI 文件名，与当前 `productName` / WiX language 后缀一致

---

## 9. 省时排障提示

- [ ] Python 运行时 / gateway **行为怪异**且日志提示 bundle 陈旧：先做 **`python/build_bundle.ps1`** 再打 MSI，而非只重复 `cargo tauri build`
- [ ] **`webviewInstallMode`**：确认目标机 WebView2 安装体验可接受（见 [tauri/tauri.conf.json](../tauri/tauri.conf.json)）

---

修订此清单时：**只增加可操作的勾选项**；泛泛的「再多测测」不写进表格。
