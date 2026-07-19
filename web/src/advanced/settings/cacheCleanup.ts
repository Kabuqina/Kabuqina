// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Browser-side state that is safe to discard from Settings -> Clear cache.
 *
 * Keep this list deliberately narrow. In particular, do not replace these
 * removals with Storage.clear(): locale, theme, font size, workbench layout,
 * the custom companion image, and the user's API-key gate choice are durable
 * preferences and must survive cache cleanup.
 */
export const VOLATILE_LOCAL_STORAGE_KEYS = [
  "kabuqina.study.context.v1",
  "kabuqina.study.flashcards.v1",
  "kabuqina.study.quiz.v1",
  "hermesdesk.shell.chat.lastSessionId",
] as const;

export const VOLATILE_SESSION_STORAGE_KEYS = ["hermesdesk.onboarding-draft"] as const;

type StorageLike = Pick<Storage, "removeItem">;
type CacheStorageLike = Pick<CacheStorage, "keys" | "delete">;

export type BrowserCacheHost = {
  readonly localStorage?: StorageLike;
  readonly sessionStorage?: StorageLike;
  readonly caches?: CacheStorageLike;
};

export type BrowserCacheCleanupResult = {
  removedCacheBuckets: number;
  errors: string[];
};

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function removeKeys(
  storage: StorageLike | undefined,
  keys: readonly string[],
  scope: string,
  errors: string[],
): void {
  if (!storage) return;
  for (const key of keys) {
    try {
      storage.removeItem(key);
    } catch (error) {
      errors.push(`${scope}:${key}: ${errorText(error)}`);
    }
  }
}

function currentBrowserHost(): BrowserCacheHost | null {
  return typeof window === "undefined" ? null : window;
}

/** Remove only explicitly volatile storage keys plus Cache Storage buckets. */
export async function clearVolatileBrowserCache(
  suppliedHost?: BrowserCacheHost | null,
): Promise<BrowserCacheCleanupResult> {
  const host = suppliedHost === undefined ? currentBrowserHost() : suppliedHost;
  const errors: string[] = [];
  if (!host) return { removedCacheBuckets: 0, errors };

  let localStorage: StorageLike | undefined;
  let sessionStorage: StorageLike | undefined;
  let cacheStorage: CacheStorageLike | undefined;

  try {
    localStorage = host.localStorage;
  } catch (error) {
    errors.push(`localStorage: ${errorText(error)}`);
  }
  try {
    sessionStorage = host.sessionStorage;
  } catch (error) {
    errors.push(`sessionStorage: ${errorText(error)}`);
  }
  try {
    cacheStorage = host.caches;
  } catch (error) {
    errors.push(`CacheStorage: ${errorText(error)}`);
  }

  removeKeys(localStorage, VOLATILE_LOCAL_STORAGE_KEYS, "localStorage", errors);
  removeKeys(sessionStorage, VOLATILE_SESSION_STORAGE_KEYS, "sessionStorage", errors);

  let removedCacheBuckets = 0;
  if (cacheStorage) {
    let names: string[] = [];
    try {
      names = await cacheStorage.keys();
    } catch (error) {
      errors.push(`CacheStorage.keys: ${errorText(error)}`);
    }
    for (const name of names) {
      try {
        if (await cacheStorage.delete(name)) removedCacheBuckets += 1;
      } catch (error) {
        errors.push(`CacheStorage:${name}: ${errorText(error)}`);
      }
    }
  }

  return { removedCacheBuckets, errors };
}
