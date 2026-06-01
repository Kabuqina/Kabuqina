// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";

export function useResolvedTheme(): "light" | "dark" {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof document === "undefined") return "light";
    const t = document.documentElement.dataset.theme;
    return t === "dark" ? "dark" : "light";
  });

  useEffect(() => {
    const el = document.documentElement;
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.type === "attributes" && m.attributeName === "data-theme") {
          setTheme(el.dataset.theme === "dark" ? "dark" : "light");
        }
      }
    });
    observer.observe(el, { attributes: true });
    return () => observer.disconnect();
  }, []);

  return theme;
}
