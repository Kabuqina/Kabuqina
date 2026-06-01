// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  type Locale,
  applyDocumentLang,
  getLocale,
  setStoredLocale,
  translate as translateCore,
} from "./i18n-core";

type I18nValue = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (path: string, params?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nValue | null>(null);

function readInitialLocale(): Locale {
  if (typeof window === "undefined") return "zh";
  return getLocale();
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLoc] = useState<Locale>(readInitialLocale);

  const setLocale = useCallback((l: Locale) => {
    setStoredLocale(l);
    applyDocumentLang(l);
    setLoc(l);
  }, []);

  useLayoutEffect(() => {
    applyDocumentLang(locale);
  }, [locale]);

  const t = useCallback(
    (path: string, params?: Record<string, string | number>) => translateCore(path, locale, params),
    [locale]
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const v = useContext(I18nContext);
  if (!v) throw new Error("useI18n must be used within I18nProvider");
  return v;
}

/** For non-React code (e.g. validate). Uses `localStorage` + zh fallback. */
export { translateCore as translate };
