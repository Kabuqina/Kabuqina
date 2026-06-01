// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useNavigate } from "react-router-dom";
import { Bot, Boxes, Package, Plug, Search, Shield, Wrench, X } from "lucide-react";
import { AppScaffold } from "../../components/AppScaffold";
import { BackButton } from "../../components/ui/BackButton";
import { Button } from "../../components/ui/Button";
import { Toggle } from "../../components/ui/Toggle";
import { cn } from "../../lib/cn";
import { useI18n } from "../../lib/i18n";

type Tab = "skills" | "tools" | "plugins";
type Role = "default" | "advanced" | "power";

type CapabilityBase = {
  name: string;
  label?: string;
  description?: string;
  roles?: Role[];
  source?: string;
  trust?: string;
  risk?: "low" | "medium" | "high" | string;
  recommended?: boolean;
  can_edit?: boolean;
  action_mode?: string;
};

type SkillItem = CapabilityBase & {
  category?: string | null;
  enabled?: boolean;
  tags?: string[];
};

type ToolsetItem = CapabilityBase & {
  enabled: boolean;
  configured: boolean;
  locked?: boolean;
  tools: string[];
};

type PluginItem = CapabilityBase & {
  version?: string;
  icon?: string;
  has_api?: boolean;
};

type CapabilityCatalog = {
  role: Role;
  skills: SkillItem[];
  toolsets: ToolsetItem[];
  plugins: PluginItem[];
};

type SkillDetail = SkillItem & {
  content?: string;
  linked_files?: Record<string, string[]> | null;
  setup_needed?: boolean;
};

type Selected =
  | { tab: "skills"; item: SkillItem; detail?: SkillDetail }
  | { tab: "tools"; item: ToolsetItem }
  | { tab: "plugins"; item: PluginItem };

const ROLE_RANK: Record<Role, number> = {
  default: 0,
  advanced: 1,
  power: 2,
};

const TABS: Array<{ id: Tab; icon: typeof Package }> = [
  { id: "skills", icon: Package },
  { id: "tools", icon: Wrench },
  { id: "plugins", icon: Plug },
];

export function CapabilitiesPage() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [catalog, setCatalog] = useState<CapabilityCatalog | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("skills");
  const [search, setSearch] = useState("");
  const [recommendedOnly, setRecommendedOnly] = useState(false);
  const [selected, setSelected] = useState<Selected | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCapabilityHint, setShowCapabilityHint] = useState(false);
  const [hintSaving, setHintSaving] = useState(false);

  const loadCatalog = useCallback(async () => {
    const result = await invoke<CapabilityCatalog>("cmd_capabilities_catalog");
    setCatalog(result);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      loadCatalog(),
      invoke<boolean>("cmd_get_show_recipe_market"),
    ])
      .then(([, showHint]) => {
        if (!cancelled) setShowCapabilityHint(!!showHint);
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadCatalog]);

  async function toggleCapabilityHint(next: boolean) {
    setHintSaving(true);
    try {
      await invoke("cmd_set_show_recipe_market", { enabled: next });
      setShowCapabilityHint(next);
      await loadCatalog();
    } catch (err) {
      setError(String(err));
    } finally {
      setHintSaving(false);
    }
  }

  const items = useMemo(() => {
    if (!catalog) return [];
    const pool =
      activeTab === "skills"
        ? catalog.skills
        : activeTab === "tools"
          ? catalog.toolsets
          : catalog.plugins;
    const q = search.trim().toLowerCase();
    return pool.filter((item) => {
      if (!isVisibleForRole(item, catalog.role)) return false;
      if (recommendedOnly && !item.recommended) return false;
      if (!q) return true;
      return [
        item.name,
        item.label,
        item.description,
        item.source,
        displayTrust(item),
        ...(item.roles ?? []),
        ...capabilitySearchExtras(item, t),
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q));
    });
  }, [activeTab, catalog, recommendedOnly, search, t]);

  async function openItem(item: SkillItem | ToolsetItem | PluginItem) {
    if (activeTab === "skills") {
      const skill = item as SkillItem;
      setSelected({ tab: "skills", item: skill });
      setDetailLoading(true);
      try {
        const detail = await invoke<SkillDetail>("cmd_capability_skill_detail", { name: skill.name });
        setSelected({ tab: "skills", item: skill, detail });
      } catch (err) {
        setError(String(err));
      } finally {
        setDetailLoading(false);
      }
      return;
    }
    if (activeTab === "tools") {
      setSelected({ tab: "tools", item: item as ToolsetItem });
      return;
    }
    setSelected({ tab: "plugins", item: item as PluginItem });
  }

  function askAgent(item: CapabilityBase, action: "edit" | "install" | "configure") {
    const prompt =
      action === "edit"
        ? `请查看并帮我编辑 skill \`${item.name}\`。先说明你建议改什么，得到确认后再通过 skill_manage 执行。`
        : `请帮我安装或配置推荐的 ${activeTab === "tools" ? "工具/工具集" : activeTab === "plugins" ? "插件" : "skill"} \`${item.name}\`。先检查来源、权限和风险，得到确认后再执行。`;
    nav("/chat", { state: { draftPrompt: prompt } });
  }

  const counts = {
    skills: catalog?.skills.length ?? 0,
    tools: catalog?.toolsets.length ?? 0,
    plugins: catalog?.plugins.length ?? 0,
  };

  const showHintToggle = catalog != null && catalog.role !== "power";

  return (
    <AppScaffold className="h-full overflow-hidden">
      <div className="mx-auto flex h-full max-w-6xl flex-col gap-5 px-[var(--hd-page-pad-x)] py-8 sm:py-10">
        <header>
          <BackButton onClick={() => nav("/chat")}>{t("settings.back")}</BackButton>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="hd-page-title">{t("capabilities.title")}</h1>
              <p className="hd-body mt-1.5 max-w-2xl">{t("capabilities.lead")}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {showHintToggle ? (
                <HintToggle
                  label={t("capabilities.hintLabel")}
                  desc={t("capabilities.hintDesc")}
                  value={showCapabilityHint}
                  saving={hintSaving}
                  onChange={toggleCapabilityHint}
                />
              ) : null}
              <RolePill role={catalog?.role} roleLabel={t("capabilities.roleLabel")} />
            </div>
          </div>
        </header>

        <div className="flex min-h-0 flex-1 gap-4">
          <aside className="w-48 shrink-0">
            <div className="flex flex-col gap-0.5 rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/45 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50">
              {TABS.map(({ id, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => {
                    setActiveTab(id);
                    setSelected(null);
                  }}
                  className={cn(
                    "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition",
                    "active:scale-[0.98]",
                    activeTab === id ? "hd-btn-segment-active shadow-sm" : "hd-btn-segment-idle",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <Icon className="h-4 w-4 shrink-0 opacity-90" />
                    {t(`capabilities.${id}`)}
                  </span>
                  <span
                    className={cn(
                      "text-xs tabular-nums",
                      activeTab === id ? "text-white/85" : "text-zinc-500 dark:text-zinc-500",
                    )}
                  >
                    {counts[id]}
                  </span>
                </button>
              ))}
            </div>
          </aside>

          <main className="hd-glass flex min-w-0 flex-1 flex-col overflow-hidden rounded-[var(--radius-shell-lg)]">
            <div className="flex flex-wrap items-center gap-3 border-b border-zinc-200/90 px-4 py-3 dark:border-zinc-700/80">
              <div className="relative min-w-64 flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t("capabilities.search")}
                  className={cn(
                    "hd-input h-10 w-full rounded-[var(--radius-shell)] pl-9 pr-9 text-sm outline-none transition",
                    "placeholder:text-[var(--kq-color-muted)] dark:placeholder:text-zinc-500",
                  )}
                />
                {search && (
                  <button
                    type="button"
                    onClick={() => setSearch("")}
                    className="hd-btn-ghost absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1.5"
                    aria-label={t("capabilities.clear")}
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400">
                <input
                  type="checkbox"
                  checked={recommendedOnly}
                  onChange={(e) => setRecommendedOnly(e.target.checked)}
                  className="size-3.5 rounded border-[var(--kq-color-border)] text-[var(--kq-color-primary)] focus:ring-[var(--kq-color-primary)] dark:border-zinc-600 dark:bg-zinc-800"
                />
                {t("capabilities.recommendedOnly")}
              </label>
            </div>

            <div className="h-[calc(100%-65px)] overflow-y-auto p-4">
              {loading ? (
                <EmptyState text={t("capabilities.loading")} />
              ) : error ? (
                <EmptyState text={error} />
              ) : items.length === 0 ? (
                <EmptyState text={t("capabilities.empty")} />
              ) : (
                <div className="grid gap-3">
                  {items.map((item) => (
                    <CapabilityRow
                      key={item.name}
                      item={item}
                      active={selected?.item.name === item.name}
                      onClick={() => openItem(item)}
                    />
                  ))}
                </div>
              )}
            </div>
          </main>

          <DetailPanel
            selected={selected}
            loading={detailLoading}
            onClose={() => setSelected(null)}
            onAskAgent={askAgent}
          />
        </div>
      </div>
    </AppScaffold>
  );
}

function CapabilityRow({
  item,
  active,
  onClick,
}: {
  item: CapabilityBase & { enabled?: boolean; locked?: boolean };
  active: boolean;
  onClick: () => void;
}) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-[var(--radius-shell-lg)] border p-4 text-left shadow-[var(--shadow-shell)] transition",
        "active:scale-[0.99]",
        active
          ? "border-[var(--kq-color-primary-light)] bg-[var(--hd-info-bg)] dark:border-[#D4C5E2]/30 dark:bg-[var(--hd-info-bg)]"
          : "hd-glass-subtle border-[var(--kq-color-border)] hover:border-[var(--kq-color-primary-light)] dark:border-zinc-700/90 dark:hover:border-[#D4C5E2]/40",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="hd-card-title">{item.label || item.name}</span>
            {item.recommended && <Badge tone="blue">{t("capabilities.badgeRecommended")}</Badge>}
            {item.enabled !== undefined && (
              <Badge tone={item.enabled ? "green" : "zinc"}>
                {item.enabled ? t("capabilities.badgeActive") : t("capabilities.badgeInactive")}
              </Badge>
            )}
            {item.locked && <Badge tone="amber">{t("capabilities.badgeLocked")}</Badge>}
          </div>
          <p className="hd-body mt-1 line-clamp-2">{item.description || t("capabilities.noDescription")}</p>
        </div>
      </div>
      <CapabilityMetaBlock item={item} className="mt-3" />
    </button>
  );
}

function DetailPanel({
  selected,
  loading,
  onClose,
  onAskAgent,
}: {
  selected: Selected | null;
  loading: boolean;
  onClose: () => void;
  onAskAgent: (item: CapabilityBase, action: "edit" | "install" | "configure") => void;
}) {
  const { t } = useI18n();

  if (!selected) {
    return (
      <aside className="hd-glass-subtle hidden w-80 shrink-0 rounded-[var(--radius-shell-lg)] border border-dashed border-zinc-300/90 p-6 text-sm text-zinc-500 dark:border-zinc-600/90 dark:text-zinc-400 lg:block">
        {t("capabilities.detailSelectItem")}
      </aside>
    );
  }

  const item = selected.item;
  const detail = selected.tab === "skills" ? selected.detail : undefined;
  const content = detail?.content;

  return (
    <aside className="hd-glass w-96 shrink-0 overflow-hidden rounded-[var(--radius-shell-lg)]">
      <div className="flex items-center justify-between border-b border-zinc-200/90 px-4 py-3 dark:border-zinc-700/80">
        <div className="flex min-w-0 items-center gap-2">
          <div className="kq-icon-well flex size-8 shrink-0 items-center justify-center rounded-lg">
            <Boxes className="h-4 w-4" />
          </div>
          <span className="truncate font-medium text-zinc-900 dark:text-zinc-100">{item.label || item.name}</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
          aria-label={t("capabilities.closePanel")}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="max-h-[calc(100vh-210px)] overflow-y-auto p-4">
        {loading ? (
          <EmptyState text={t("capabilities.detailLoading")} />
        ) : (
          <div className="space-y-4">
            <p className="hd-body">{item.description || detail?.description || t("capabilities.noDescription")}</p>
            <CapabilityMetaBlock item={item} />
            {selected.tab === "tools" && (
              <ToolDetails item={selected.item} />
            )}
            {selected.tab === "plugins" && (
              <PluginDetails item={selected.item} />
            )}
            {detail?.linked_files && (
              <div>
                <h3 className="hd-section-title mb-2">{t("capabilities.linkedFiles")}</h3>
                <div className="space-y-2">
                  {Object.entries(detail.linked_files).map(([group, files]) => (
                    <div key={group} className="rounded-[var(--radius-shell)] bg-zinc-100 p-3 text-xs dark:bg-zinc-800/80">
                      <div className="mb-1 font-medium">{group}</div>
                      {files.map((file) => (
                        <div key={file} className="font-mono text-zinc-500">{file}</div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {content && (
              <pre className="hd-mono max-h-80 overflow-auto rounded-[var(--radius-shell)] bg-zinc-950 p-3 text-xs leading-relaxed text-zinc-100">
                {content}
              </pre>
            )}
            <div className="flex flex-wrap gap-2 border-t border-zinc-200/90 pt-4 dark:border-zinc-700/80">
              {selected.tab === "skills" && item.can_edit && (
                <Button variant="primary" size="sm" onClick={() => onAskAgent(item, "edit")}>
                  <Bot className="h-3.5 w-3.5" />
                  {t("capabilities.askAgentEdit")}
                </Button>
              )}
              {selected.tab !== "skills" && (
                <Button variant="primary" size="sm" onClick={() => onAskAgent(item, selected.tab === "tools" ? "configure" : "install")}>
                  <Bot className="h-3.5 w-3.5" />
                  {t("capabilities.askAgent")}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

function ToolDetails({ item }: { item: ToolsetItem }) {
  const { t } = useI18n();
  return (
    <div>
      <h3 className="hd-section-title mb-2">{t("capabilities.toolsHeading")}</h3>
      <div className="flex flex-wrap gap-1.5">
        {item.tools.map((tool) => (
          <Badge key={tool} tone="zinc">{tool}</Badge>
        ))}
        {item.tools.length === 0 && <span className="text-xs text-zinc-500">{t("capabilities.noToolsListed")}</span>}
      </div>
    </div>
  );
}

function PluginDetails({ item }: { item: PluginItem }) {
  const { t } = useI18n();
  return (
    <div className="grid gap-2 text-sm">
      <InfoRow label={t("capabilities.pluginVersion")} value={item.version || t("capabilities.pluginUnknown")} />
      <InfoRow label={t("capabilities.pluginApi")} value={item.has_api ? t("capabilities.pluginYes") : t("capabilities.pluginNo")} />
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 rounded-[var(--radius-shell)] bg-zinc-100 px-3 py-2 dark:bg-zinc-800/90">
      <span className="text-zinc-500">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function RolePill({ role, roleLabel }: { role?: Role; roleLabel: string }) {
  const { t } = useI18n();
  const roleText = role ? t(`capabilities.roleNames.${role}`) : t("capabilities.roleLoading");
  return (
    <div className="hd-glass-subtle flex items-center gap-2 px-3 py-2 text-sm">
      <div className="kq-icon-well flex size-8 shrink-0 items-center justify-center rounded-lg">
        <Shield className="h-4 w-4" />
      </div>
      <span className="text-zinc-500 dark:text-zinc-400">{roleLabel}</span>
      <span className="font-medium text-zinc-900 dark:text-zinc-100">{roleText}</span>
    </div>
  );
}

function HintToggle({
  label,
  desc,
  value,
  saving,
  onChange,
}: {
  label: string;
  desc: string;
  value: boolean;
  saving: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <div className="hd-glass-subtle flex items-center gap-3 px-3 py-2 text-sm">
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-zinc-700 dark:text-zinc-200">{label}</div>
        <div className="text-[11px] leading-snug text-zinc-500 dark:text-zinc-400">{desc}</div>
      </div>
      <Toggle value={value} disabled={saving} onChange={onChange} />
    </div>
  );
}

function CapabilityMetaBlock({ item, className }: { item: CapabilityBase; className?: string }) {
  const { t } = useI18n();
  const trustRaw = displayTrust(item);
  const srcRaw = displaySource(item);
  const src = formatCapabilityToken(`capabilities.token.source.${normTokenKey(srcRaw)}`, srcRaw, t);
  const trust = formatCapabilityToken(`capabilities.token.trust.${normTokenKey(trustRaw)}`, trustRaw, t);
  const roles = item.roles ?? [];
  const joiner = t("capabilities.meta.rolesJoiner");
  const rolesText =
    roles.length === 0
      ? t("capabilities.meta.rolesAll")
      : roles.map((r) => t(`capabilities.roleNames.${r}`)).join(joiner);
  const riskKey = normTokenKey((item.risk || "low").toString());
  const riskLabel = formatCapabilityToken(`capabilities.token.risk.${riskKey}`, (item.risk || "low").toString(), t);
  const riskClass =
    riskKey === "high"
      ? "text-red-600 dark:text-red-400"
      : riskKey === "medium"
        ? "text-amber-600 dark:text-amber-400"
        : "text-emerald-600 dark:text-emerald-400";

  return (
    <dl className={cn("grid gap-1 text-[11px] leading-snug sm:text-xs", className)}>
      <div className="flex flex-wrap gap-x-1 [word-break:break-word]">
        <dt className="hd-meta shrink-0">{t("capabilities.meta.source")}</dt>
        <dd className="min-w-0 font-medium text-zinc-900 dark:text-zinc-100">{src}</dd>
      </div>
      <div className="flex flex-wrap gap-x-1 [word-break:break-word]">
        <dt className="hd-meta shrink-0">{t("capabilities.meta.trust")}</dt>
        <dd className="min-w-0 font-medium text-zinc-900 dark:text-zinc-100">{trust}</dd>
      </div>
      <div className="flex flex-wrap gap-x-1 [word-break:break-word]">
        <dt className="hd-meta shrink-0">{t("capabilities.meta.roles")}</dt>
        <dd className="min-w-0 font-medium text-zinc-900 dark:text-zinc-100">{rolesText}</dd>
      </div>
      <div className="flex flex-wrap gap-x-1 [word-break:break-word]">
        <dt className="hd-meta shrink-0">{t("capabilities.meta.risk")}</dt>
        <dd className={cn("min-w-0 font-medium", riskClass)}>{riskLabel}</dd>
      </div>
    </dl>
  );
}

function Badge({ tone, children }: { tone: "green" | "amber" | "red" | "blue" | "zinc"; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[var(--radius-shell-pill)] px-2 py-0.5 text-[11px] font-medium",
        tone === "green" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
        tone === "amber" && "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
        tone === "red" && "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
        tone === "blue" && "bg-[var(--kq-color-primary-pale)] text-[var(--kq-color-strong)] dark:bg-[#D4C5E2]/15 dark:text-[#D4C5E2]",
        tone === "zinc" && "bg-zinc-100 text-zinc-600 dark:bg-zinc-800/90 dark:text-zinc-300",
      )}
    >
      {children}
    </span>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex h-full min-h-40 items-center justify-center rounded-[var(--radius-shell-lg)] border border-dashed border-zinc-300/90 bg-zinc-50/50 p-8 text-center text-sm text-zinc-500 dark:border-zinc-600/90 dark:bg-zinc-900/30 dark:text-zinc-400">
      {text}
    </div>
  );
}

function isVisibleForRole(item: CapabilityBase, role: Role): boolean {
  const roles = item.roles ?? [];
  if (roles.length === 0) return true;
  const itemMinRank = Math.min(...roles.map((r) => ROLE_RANK[r]));
  return ROLE_RANK[role] >= itemMinRank && roles.includes(role);
}

function displayTrust(item: CapabilityBase): string {
  const raw = (item.trust || "").trim().toLowerCase();
  if (raw && raw !== "unknown") return raw;
  const source = (item.source || "").trim().toLowerCase();
  if (
    source === "official" ||
    source === "builtin" ||
    source === "bundled" ||
    source === "installed" ||
    source === "user" ||
    source === "project"
  ) {
    return "official";
  }
  return raw || "unknown";
}

function displaySource(item: CapabilityBase): string {
  const s = (item.source || "").trim();
  return s || "installed";
}

function normTokenKey(raw: string): string {
  return raw.trim().toLowerCase().replace(/-/g, "_");
}

function formatCapabilityToken(path: string, fallback: string, t: (p: string) => string): string {
  const out = t(path);
  return out === path ? fallback : out;
}

function capabilitySearchExtras(item: CapabilityBase, t: (p: string) => string): string[] {
  const trustRaw = displayTrust(item);
  const srcRaw = displaySource(item);
  const srcPath = `capabilities.token.source.${normTokenKey(srcRaw)}`;
  const trustPath = `capabilities.token.trust.${normTokenKey(trustRaw)}`;
  const riskPath = `capabilities.token.risk.${normTokenKey((item.risk || "low").toString())}`;
  const extras = [t(srcPath), t(trustPath), t(riskPath)];
  for (const r of item.roles ?? []) {
    extras.push(t(`capabilities.roleNames.${r}`));
  }
  extras.push(t("capabilities.meta.rolesAll"));
  return extras;
}
