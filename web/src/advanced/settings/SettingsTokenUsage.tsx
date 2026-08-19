// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { Gauge } from "lucide-react";
import { Section } from "../../components/ui/Section";
import { useI18n } from "../../lib/i18n";
import { cn } from "../../lib/cn";
import {
  cmdStudyTokenUsage,
  type StudyTokenUsageResponse,
  type StudyTokenUsageWindow,
} from "../../chat/study/study-api";

/**
 * token 用量。
 *
 * **只报 token 数，不折算金额**（owner 定）：定价、折扣、缓存命中都不在我们手里，
 * 报一个假精度的钱数比不报更糟。
 *
 * 展示口径按设置规格 §2.2：本周 / 本月 + 按课程分组，低强调数字，**不做趋势图**——
 * 学生看完能执行的动作是"少问几次"或"换个便宜模型"，一张折线图不增加这个决策
 * （信息原则 §7.4 行动测试）。
 *
 * `incomplete` 要说出来：它表示有成功的调用没有回报 token 数，合计因此是**下限**
 * 而不是准确值。默默少报和报假精度是同一种不诚实。
 */
export function SettingsTokenUsage() {
  const { t, locale } = useI18n();
  const [window_, setWindow] = useState<StudyTokenUsageWindow>("week");
  const [data, setData] = useState<StudyTokenUsageResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  const load = useCallback((next: StudyTokenUsageWindow) => {
    setState("loading");
    cmdStudyTokenUsage(next)
      .then((result) => {
        setData(result);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, []);

  useEffect(() => load(window_), [load, window_]);

  const fmt = (value: number) => value.toLocaleString(locale === "en" ? "en-US" : "zh-CN");

  return (
    <Section icon={Gauge} title={t("settings.usageTitle")} desc={t("settings.usageDesc")}>
      <div className="space-y-4">
        <div
          role="tablist"
          aria-label={t("settings.usageWindowLabel")}
          className="inline-flex rounded-2xl border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/45 p-1 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]"
        >
          {(["week", "month"] as const).map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={window_ === id}
              onClick={() => setWindow(id)}
              className={cn(
                "min-h-[2rem] rounded-xl px-3 py-1 text-sm font-medium transition",
                window_ === id ? "hd-btn-segment-active shadow-sm" : "hd-btn-segment-idle",
              )}
            >
              {t(id === "week" ? "settings.usageWeek" : "settings.usageMonth")}
            </button>
          ))}
        </div>

        {state === "loading" ? (
          /* 骨架照着读完后的形状排：一个大数字 + 一行明细 + 两条清单，
             这样数据落位时版面不跳。文字仍留给读屏器。 */
          <div className="space-y-3" role="status" aria-busy="true">
            <span className="sr-only">{t("settings.usageLoading")}</span>
            <div className="kq-skeleton h-7 w-32" />
            <div className="kq-skeleton h-4 w-3/5" />
            <div className="space-y-2 border-t border-[var(--kq-color-border)] pt-3">
              <div className="kq-skeleton h-4 w-4/5" />
              <div className="kq-skeleton h-4 w-2/3" />
            </div>
          </div>
        ) : null}

        {state === "error" ? (
          <p className="text-sm text-[var(--kq-color-muted)]" role="status">
            {t("settings.usageUnavailable")}
          </p>
        ) : null}

        {state === "ready" && data ? (
          data.totals.succeededAttempts === 0 ? (
            <p className="text-sm text-[var(--kq-color-muted)]">{t("settings.usageEmpty")}</p>
          ) : (
            <>
              <div className="space-y-1">
                <p className="text-2xl font-semibold tabular-nums text-[var(--kq-color-strong)]">
                  {fmt(data.totals.totalTokens)}
                </p>
                <p className="text-sm text-[var(--kq-color-muted)]">
                  {t("settings.usageBreakdown", {
                    input: fmt(data.totals.inputTokens),
                    output: fmt(data.totals.outputTokens),
                  })}
                </p>
                {data.totals.incomplete ? (
                  <p className="text-sm text-[var(--kq-color-muted)]">{t("settings.usageIncomplete")}</p>
                ) : null}
              </div>

              <ul className="space-y-2 border-t border-[var(--kq-color-border)] pt-3">
                {data.courses.map((course) => (
                  <li key={course.spaceId} className="space-y-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                      <span className="text-sm text-[var(--kq-color-ink)]">{course.title}</span>
                      <span className="text-sm tabular-nums text-[var(--kq-color-strong)]">
                        {fmt(course.totalTokens)}
                      </span>
                    </div>
                    {course.models.map((model) => (
                      <div
                        key={`${model.providerId}:${model.modelId}`}
                        className="flex flex-wrap items-baseline justify-between gap-x-3 pl-3 text-xs text-[var(--kq-color-muted)]"
                      >
                        <span>{model.modelId}</span>
                        <span className="tabular-nums">{fmt(model.totalTokens)}</span>
                      </div>
                    ))}
                  </li>
                ))}
              </ul>
            </>
          )
        ) : null}
      </div>
    </Section>
  );
}
