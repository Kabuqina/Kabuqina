// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { VoxelIcon } from "../components/voxel/VoxelIcon";
import { ART_ASSETS } from "../lib/artAssets";
import { useI18n } from "../lib/i18n";
import { getStoredThemeMode, resolveTheme, setThemeMode, type ResolvedTheme } from "../lib/ui-prefs";
import { WindowControls } from "../components/WindowControls";
import { onOpenActivityRequest } from "./activityBridge";
import { ActivityPanel } from "./ActivityPanel";
import "./appShell.css";

/**
 * 全局外壳（架构 §5.1，原型 `AppHeader`）。
 *
 * 自习与对话两个目的地始终都在，站在台灯右边；Settings 是右侧工具。（Studio 已砍）
 * 台灯属于小娜的品牌人格，横条最左端是它；Logo 与名称在正中。
 * 「进行中」不在这条横条上——它搬进了 Chat 的抽屉：横条上不该有第二处会跳数字的东西。
 * 能力目录与网关目的地已经从产品面退场，所以这里只有这几样。
 *
 * 这条页眉**就是**产品面与辅助流程的窗口标题栏：整条可拖拽，最右端是缩到小娜与
 * 系统窗口控制（`WindowControls`）。只有启动页和独立预览页使用较矮的
 * `WindowTitleBar`。全窗口任何时候都只有一条横条。
 */

type Surface = "study" | "chat" | "settings" | null;

function surfaceOf(pathname: string): Surface {
  if (pathname.startsWith("/study")) return "study";
  if (pathname.startsWith("/chat") || pathname.startsWith("/export")) return "chat";
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
      {/* 全窗口只有这一条横条：台灯与两个目的地在左侧，品牌在正中，
          设置与窗口控制在右侧。整条是拖拽区，交互件各自 no-drag。 */}
      <header className="kq-app-header hermes-titlebar-drag" data-tauri-drag-region>
        <div className="kq-left-cluster hermes-titlebar-nodrag">
          {/* 台灯属于小娜的品牌人格，但它自己站在最左端——桌面上最靠边的东西。 */}
          <button
            type="button"
            className={`kq-lamp-toggle ${theme === "dark" ? "is-on" : ""}`}
            aria-label={theme === "dark" ? t("appShell.lampOff") : t("appShell.lampOn")}
            aria-pressed={theme === "dark"}
            onClick={toggleLamp}
          >
            {/* 灯是**物件**不是字形：亮/灭换的是灯泡材质（玻璃 ↔ 火把橙），
                不是给同一个线条图标换颜色。 */}
            <VoxelIcon art={theme === "dark" ? "lampLit" : "lamp"} size={30} />
          </button>
          <div className="kq-left-tools">
            {/* 两个目的地始终都在（设计稿 5）：当前那个是木头上摆的一小片纸，
                另一个是擦亮的一块木头。原来是一颗按所在面切换的按钮。 */}
            <button
              type="button"
              aria-current={surface === "study" ? "page" : undefined}
              onClick={() => navigate("/study")}
            >
              <VoxelIcon art="study" size={22} />
              <span>{t("appShell.study")}</span>
            </button>
            <button
              type="button"
              aria-current={surface === "chat" ? "page" : undefined}
              onClick={() => navigate("/chat")}
            >
              <VoxelIcon art="chat" size={22} />
              <span>{t("appShell.chat")}</span>
            </button>
          </div>
        </div>

        {/* 品牌 lockup 是 grid 的中间列，两侧 1fr 对称，所以它水平居中。 */}
        <button
          className="kq-brand-lockup hermes-titlebar-nodrag"
          type="button"
          onClick={() => navigate("/study")}
        >
          {/* 正中只有注册字标，没有图形 mark（设计稿第四轮 4a）——横条上已经有五件
              体素物件，再摆一只小娜杯就成了图标堆；字标自己带着杯口那个 Q。
              字标是注册字形的位图，不是文字：Qi 那两个字母的字面与墨色都在图里，
              系统字体拼不出来。白天/夜晚换的是文件，不是滤镜。 */}
          <img
            className="kq-brand-name"
            src={theme === "dark" ? ART_ASSETS.wordmarkNight : ART_ASSETS.wordmark}
            alt={t("appShell.brand")}
          />
        </button>

        <div className="kq-utility-nav hermes-titlebar-nodrag">
          <button
            type="button"
            aria-label={t("appShell.settings")}
            aria-current={surface === "settings" ? "page" : undefined}
            onClick={() => navigate("/settings")}
          >
            <VoxelIcon art="settings" size={28} />
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
