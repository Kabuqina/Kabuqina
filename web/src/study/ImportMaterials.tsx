// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { FilePlus2, Loader2, X } from "lucide-react";
import { useI18n } from "../lib/i18n";
import {
  cmdStudyMaterialRead,
  cmdStudyPreferencesGet,
  type StudyImportReadMode,
} from "../chat/study/study-api";

/** docling 已接入的格式（架构 §2.1.1）。 */
const EXTENSIONS = ["pdf", "docx", "pptx", "xlsx", "md", "html", "csv", "png", "jpg", "jpeg", "webp"];

const MODES: StudyImportReadMode[] = ["auto", "precise", "math"];

type FileState = {
  path: string;
  name: string;
  status: "pending" | "reading" | "done" | "failed";
  /** 后端实际用的档位；被偏好上限压下来时与请求档位不同。 */
  effectiveMode?: StudyImportReadMode;
  limited?: boolean;
  error?: string;
};

/** 读完之后 shell 还要接着说的两件事：读进了几份、有几份被压回了偏好档位。 */
export type StudyImportResult = { paths: string[]; limited: number };

function baseName(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

/**
 * 材料导入（架构 §2.1.1：学生自己导入是**默认路径**）。
 *
 * 这一步只做"把材料读进来"。读完两份以上时，分课与目录的判断由小娜提出、学生确认
 * （§2.1.2），那是下一步，不在这里替他决定。
 *
 * 档位的两条诚实规则（账本 B-2）：
 * - 默认跟设置里的偏好走，**不传 requestedMode**；
 * - 学生临时选了比偏好更重的档位，先说清要花多久，确认后才带 `overrideLimit`；
 *   不确认的话后端会降到偏好档位并以 `limited` 明示，不会静默把 CPU 推理跑起来。
 */
export function ImportMaterials({
  spaceId,
  onClose,
  onImported,
}: {
  spaceId: string;
  onClose: () => void;
  onImported?: (result: StudyImportResult) => void;
}) {
  const { t } = useI18n();
  const [files, setFiles] = useState<FileState[]>([]);
  const [preferred, setPreferred] = useState<StudyImportReadMode | null>(null);
  const [mode, setMode] = useState<StudyImportReadMode | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    cmdStudyPreferencesGet()
      .then((prefs) => setPreferred(prefs.importReadMode))
      .catch(() => setPreferred(null));
  }, []);

  const chosen = mode ?? preferred ?? "auto";
  const heavier = preferred ? MODES.indexOf(chosen) > MODES.indexOf(preferred) : false;

  const pick = async () => {
    const picked = await open({
      title: t("study.importPickTitle"),
      multiple: true,
      filters: [{ name: t("study.importFileKind"), extensions: EXTENSIONS }],
    });
    if (!picked) return;
    const paths = Array.isArray(picked) ? picked : [picked];
    setFiles((current) => {
      const seen = new Set(current.map((f) => f.path));
      return [
        ...current,
        ...paths
          .filter((path) => !seen.has(path))
          .map((path) => ({ path, name: baseName(path), status: "pending" as const })),
      ];
    });
  };

  const start = async () => {
    setBusy(true);
    setFailed(false);
    const done: string[] = [];
    // 后端把档位压回偏好时要说出来（账本 B-2）。弹窗关掉之后这句话由 shell 接着说。
    let limited = 0;
    let anyFailed = false;
    for (const file of files) {
      if (file.status === "done") continue;
      setFiles((cur) => cur.map((f) => (f.path === file.path ? { ...f, status: "reading" } : f)));
      try {
        const isPdf = file.path.toLocaleLowerCase().endsWith(".pdf");
        const result = await cmdStudyMaterialRead({
          spaceId,
          pathStr: file.path,
          // 建课先读结构页并留下 read-cache；正文在阅读器中按页读取。
          // 这避免一本 300 页教材把桌面接口同步占住几分钟。
          includeContent: false,
          ...(isPdf ? { pageStart: 1, pageEnd: chosen === "math" ? 2 : 12 } : {}),
          // 没显式选档就不传，让后端用偏好——别把默认值在前端复制一份。
          ...(mode ? { requestedMode: mode } : {}),
          ...(mode && heavier ? { overrideLimit: true } : {}),
        });
        done.push(file.path);
        if (result.limited) limited += 1;
        setFiles((cur) =>
          cur.map((f) =>
            f.path === file.path
              ? { ...f, status: "done", effectiveMode: result.effectiveMode, limited: result.limited }
              : f,
          ),
        );
      } catch (error) {
        anyFailed = true;
        setFailed(true);
        const detail = error && typeof error === "object" && "detail" in error
          ? String((error as { detail?: unknown }).detail || "")
          : error instanceof Error
            ? error.message
            : "";
        setFiles((cur) => cur.map((f) => (
          f.path === file.path ? { ...f, status: "failed", error: detail } : f
        )));
      }
    }
    setBusy(false);
    if (!done.length) return;
    onImported?.({ paths: done, limited });
    // 读完就退出：提示落在学生返回的那一页上，不把他留在弹窗里自己关。
    // 但有读失败的就留下——哪一份没读成功只有这张列表说得清，
    // 关掉等于把失败悄悄咽了。
    if (!anyFailed) onClose();
  };

  const pending = files.some((f) => f.status === "pending" || f.status === "failed");

  return (
    <div className="kq-studio-dialog-backdrop" role="presentation">
      <section
        className="kq-studio-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={t("study.importTitle")}
      >
        <header>
          <h2>{t("study.importTitle")}</h2>
          <button type="button" onClick={onClose} aria-label={t("study.importClose")} disabled={busy}>
            <X aria-hidden />
          </button>
        </header>

        <p className="kq-studio-muted">{t("study.importLead")}</p>

        <div className="kq-studio-actions">
          <button type="button" className="kq-studio-secondary" onClick={() => void pick()} disabled={busy}>
            <FilePlus2 aria-hidden />
            {t("study.importPick")}
          </button>
        </div>

        {files.length ? (
          <ul className="kq-studio-pick-list">
            {files.map((file) => (
              <li key={file.path}>
                <span className="kq-import-row">
                  <strong>{file.name}</strong>
                  <small>
                    {file.status === "reading" ? t("study.importReading") : null}
                    {file.status === "failed" ? t("study.importFileFailed") : null}
                    {file.status === "done" && file.effectiveMode
                      ? t(
                          file.limited ? "study.importDoneLimited" : "study.importDone",
                          { mode: t(`settings.readMode.${file.effectiveMode}`) },
                        )
                      : null}
                  </small>
                  {file.status === "failed" && file.error ? <small>{file.error}</small> : null}
                </span>
              </li>
            ))}
          </ul>
        ) : null}

        {files.length ? (
          <label className="kq-studio-field">
            <span>{t("study.importReadModeLabel")}</span>
            <select
              value={chosen}
              disabled={busy}
              onChange={(event) => setMode(event.currentTarget.value as StudyImportReadMode)}
            >
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {t(`settings.readMode.${m}`)}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {/* 比偏好更重时先把代价说清楚，再让他确认——别静默跑 CPU 推理。 */}
        {heavier ? (
          <p className="kq-studio-readonly-note">{t("study.importHeavyWarning")}</p>
        ) : null}

        {failed ? (
          <p className="kq-studio-dialog-error" role="alert">
            {t("study.importFailed")}
          </p>
        ) : null}

        <div className="kq-studio-actions">
          <button
            type="button"
            className="kq-studio-primary"
            onClick={() => void start()}
            disabled={busy || !pending}
          >
            {busy ? <Loader2 className="kq-spin" aria-hidden /> : null}
            {t(heavier ? "study.importStartHeavy" : "study.importStart")}
          </button>
        </div>

      </section>
    </div>
  );
}
