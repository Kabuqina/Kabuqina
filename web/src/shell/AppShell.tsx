// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { BookOpen, FolderOpen, LampDesk, ListTodo, MessageCircle, Settings as SettingsIcon } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { getStoredThemeMode, resolveTheme, setThemeMode, type ResolvedTheme } from "../lib/ui-prefs";
import { WindowControls } from "../components/WindowControls";
import { requestOpenActivity } from "./activityBridge";
import { onOpenActivityRequest } from "./activityBridge";
import { ActivityPanel } from "./ActivityPanel";
import "./appShell.css";

/**
 * 全局外壳（架构 §5.1，原型 `AppHeader`）。
 *
 * Study 与 Studio 是两个一级目的地；Chat、进行中与 Settings 是右侧工具。
 * 台灯属于小娜的品牌人格，所以和 Logo、名称一起留在左侧品牌区。
 * 能力目录与网关目的地已经从产品面退场，所以这里只有这几样。
 *
 * 这条页眉**就是**这些产品面上的窗口标题栏：整条可拖拽，最右端是缩到小娜与系统窗口
 * 控制（`WindowControls`）。引导、导出、启动页不走这里，由 `WindowTitleBar` 画一条
 * 更矮的。全窗口任何时候都只有一条横条。
 */

type Surface = "study" | "studio" | "chat" | "settings" | null;

function surfaceOf(pathname: string): Surface {
  if (pathname.startsWith("/study")) return "study";
  if (pathname.startsWith("/studio")) return "studio";
  if (pathname.startsWith("/chat")) return "chat";
  if (pathname.startsWith("/settings")) return "settings";
  return null;
}

/**
 * 台灯是**开关**，不是三档选择器：桌上那盏灯只有开和关。
 * 「跟随系统」仍然活着，但它属于设置页那面镜子——在这里点一下就等于
 * 明确表态，所以从 system 出发时先解析当前实际是哪一档，再翻到另一档。
 */
function useLampTheme(): [ResolvedTheme, () => void] {
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolveTheme(getStoredThemeMode()));

  useEffect(() => {
    const sync = () => setResolved(resolveTheme(getStoredThemeMode()));
    // 设置页那面镜子改了主题，桌上的灯要跟着亮/灭。
    window.addEventListener("storage", sync);
    // 与 ui-prefs 同样的守卫：没有 matchMedia 的环境（测试宿主）不该让页眉崩掉。
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    mq?.addEventListener("change", sync);
    return () => {
      mq?.removeEventListener("change", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  // 副作用不能塞进 state updater：StrictMode 下 updater 会跑两次，
  // 结果是 DOM 翻了而灯没亮。从当前实际解析值算下一档，写完再同步 state。
  const toggle = useCallback(() => {
    const next: ResolvedTheme = resolveTheme(getStoredThemeMode()) === "dark" ? "light" : "dark";
    setThemeMode(next);
    setResolved(next);
  }, []);

  return [resolved, toggle];
}

export function AppShell() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const surface = surfaceOf(location.pathname);
  const [theme, toggleLamp] = useLampTheme();
  const [activityOpen, setActivityOpen] = useState(false);

  useEffect(() => onOpenActivityRequest(() => setActivityOpen(true)), []);

  return (
    <div className="kq-app-frame" data-surface={surface ?? undefined}>
      {/* 全窗口只有这一条横条：产品导航在中间，窗口控制在最右端。
          整条是拖拽区，交互件各自 no-drag。 */}
      <header className="kq-app-header hermes-titlebar-drag" data-tauri-drag-region>
        <div className="kq-brand-cluster hermes-titlebar-nodrag">
          <button
            className="kq-brand-lockup"
            type="button"
            onClick={() => navigate("/study")}
          >
            <span className="kq-brand-mark" aria-hidden>K</span>
            <span className="kq-brand-name">{t("appShell.brand")}</span>
          </button>
          <button
            type="button"
            className={`kq-lamp-toggle ${theme === "dark" ? "is-on" : ""}`}
            aria-label={theme === "dark" ? t("appShell.lampOff") : t("appShell.lampOn")}
            aria-pressed={theme === "dark"}
            onClick={toggleLamp}
          >
            <LampDesk aria-hidden size={20} />
          </button>
        </div>

        <nav className="kq-primary-nav hermes-titlebar-nodrag" aria-label={t("appShell.primaryNav")}>
          <button
            type="button"
            aria-current={surface === "study" ? "page" : undefined}
            onClick={() => navigate("/study")}
          >
            <BookOpen aria-hidden size={18} />
            {t("appShell.study")}
          </button>
          <button
            type="button"
            aria-current={surface === "studio" ? "page" : undefined}
            onClick={() => navigate("/studio")}
          >
            <FolderOpen aria-hidden size={18} />
            {t("appShell.studio")}
          </button>
        </nav>

        <div className="kq-utility-nav hermes-titlebar-nodrag">
          <button
            type="button"
            aria-current={surface === "chat" ? "page" : undefined}
            onClick={() => navigate("/chat")}
          >
            <MessageCircle aria-hidden size={18} />
            <span>{t("appShell.chat")}</span>
          </button>
          <button
            type="button"
            aria-expanded={activityOpen}
            aria-controls="kq-global-activity"
            onClick={() => requestOpenActivity()}
          >
            <ListTodo aria-hidden size={16} />
            <span>{t("appShell.activity")}</span>
          </button>
          <button
            type="button"
            aria-label={t("appShell.settings")}
            aria-current={surface === "settings" ? "page" : undefined}
            onClick={() => navigate("/settings")}
          >
            <SettingsIcon aria-hidden size={19} />
          </button>
          {/* 产品控制与窗口控制之间留一道分隔：前者管应用，后者管这扇窗。 */}
          <WindowControls />
        </div>
      </header>

      <ActivityPanel
        open={activityOpen}
        onClose={() => setActivityOpen(false)}
        onReturn={(target) => {
          setActivityOpen(false);
          navigate(target);
        }}
      />

      <div className="kq-app-surface">
        <Outlet />
      </div>
    </div>
  );
}
