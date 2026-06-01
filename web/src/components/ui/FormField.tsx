// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { cn } from "../../lib/cn";

type FieldType = "text" | "password" | "select" | "textarea";

type SelectOption = { label: string; value: string };

type Props = {
  id?: string;
  label: string;
  description?: string;
  type?: FieldType;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  options?: SelectOption[];
  className?: string;
  autoComplete?: string;
  spellCheck?: boolean;
};

export const inputBase = "hd-input font-mono dark:border-zinc-700 dark:bg-zinc-900/90 dark:text-zinc-100";

export function FormField({
  id,
  label,
  description,
  type = "text",
  value,
  onChange,
  placeholder,
  options,
  className,
  autoComplete = "off",
  spellCheck = false,
}: Props) {
  const fieldId = id ?? label;
  return (
    <div className={cn("space-y-1.5", className)}>
      <label
        htmlFor={fieldId}
        className="block text-sm font-medium text-[var(--kq-color-strong)] dark:text-zinc-200"
      >
        {label}
      </label>
      {description ? (
        <p className="text-xs leading-relaxed text-[var(--kq-color-muted)] dark:text-zinc-400">
          {description}
        </p>
      ) : null}
      {type === "select" ? (
        <select
          id={fieldId}
          className={cn(inputBase, "cursor-pointer")}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          {options?.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ) : type === "textarea" ? (
        <textarea
          id={fieldId}
          className={cn(inputBase, "min-h-[5rem] resize-y")}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          spellCheck={spellCheck}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          id={fieldId}
          type={type}
          className={inputBase}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          spellCheck={spellCheck}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </div>
  );
}
