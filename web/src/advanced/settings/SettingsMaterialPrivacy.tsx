// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { ShieldCheck } from "lucide-react";
import { Section } from "../../components/ui/Section";
import { useI18n } from "../../lib/i18n";
import type { LlmConfigPreview } from "../../lib/llm-config";

/**
 * 材料与隐私披露。
 *
 * 默认路径是学生导入**自己的教材**——那本书有版权，页边还有他自己的批注。产品因此欠他
 * 一句话：哪些内容离开这台机器、发给谁。
 *
 * 这一节是**披露**，不是一堆开关：能关的只有"已经是可选项"的东西，把不可选的做成假开关
 * 更不诚实。文案标准照抄「学习功能改进计数」那一节——具体、可核对、不含糊。
 *
 * 每一条都对着代码核过，宁少说不多说：
 * - 解析在本机：docling 在本地跑（版面/表格/公式模型都在本机推理）；
 * - 对话附件会外发：`DeskAttachmentPayload` 带 `data` 字段，即文件内容本身；
 * - 讲解与纠错只发编号：`TutorProviderRequestV1.input_refs` 是 `{kind, id}` 形态的
 *   条目引用（见 learning_data_service 对 `ref.kind === "artifact"` 的校验），
 *   连同 `goal` 一起发出，**材料正文不在其中**；
 * - 学习记录留本机：证据写在本地 learning 库里。
 */
export function SettingsMaterialPrivacy() {
  const { t } = useI18n();
  const [preview, setPreview] = useState<LlmConfigPreview | null>(null);

  useEffect(() => {
    let alive = true;
    invoke<LlmConfigPreview>("cmd_llm_config_preview")
      .then((value) => { if (alive) setPreview(value); })
      .catch(() => { /* 取不到就退回不点名的说法，不阻塞这一节 */ });
    return () => { alive = false; };
  }, []);

  const providerLabel = preview?.model
    ? `${preview.provider ?? preview.host ?? ""} · ${preview.model}`.replace(/^ · /, "")
    : (preview?.provider ?? preview?.host ?? null);

  const lines: Array<{ key: string; sends: boolean }> = [
    { key: "privacyLocalParse", sends: false },
    { key: "privacyTutorRefs", sends: false },
    { key: "privacyLocalRecords", sends: false },
    { key: "privacyChatAttachments", sends: true },
  ];

  return (
    <Section
      icon={ShieldCheck}
      title={t("settings.privacyTitle")}
      desc={t("settings.privacyDesc")}
    >
      <div className="space-y-3">
        <ul className="space-y-2">
          {lines.map(({ key, sends }) => (
            <li key={key} className="flex items-start gap-2.5 text-sm leading-relaxed">
              <span
                aria-hidden
                className={`mt-1.5 inline-block size-1.5 shrink-0 rounded-full ${
                  sends ? "bg-amber-500" : "bg-emerald-500"
                }`}
              />
              <span className="text-[var(--kq-color-ink)]">{t(`settings.${key}`)}</span>
            </li>
          ))}
        </ul>
        <p className="border-t border-[var(--kq-color-border)] pt-3 text-sm leading-relaxed text-[var(--kq-color-muted)]">
          {providerLabel
            ? t("settings.privacyProvider", { provider: providerLabel })
            : t("settings.privacyProviderUnset")}
        </p>
      </div>
    </Section>
  );
}
