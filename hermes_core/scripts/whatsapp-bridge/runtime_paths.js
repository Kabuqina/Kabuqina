import path from 'path';

export function resolveRuntimePaths(sessionArg = '', cacheRootArg = '', env = process.env) {
  const userHome = env.HOME || env.USERPROFILE || process.cwd();
  const kabuqinaHome = env.KABUQINA_HOME || env.HERMES_HOME || path.join(userHome, '.kabuqina');
  const sessionDir = sessionArg || path.join(kabuqinaHome, 'platforms', 'whatsapp', 'session');
  const cacheRoot = cacheRootArg || path.join(kabuqinaHome, 'cache');
  return {
    sessionDir,
    imageCacheDir: path.join(cacheRoot, 'images'),
    documentCacheDir: path.join(cacheRoot, 'documents'),
    audioCacheDir: path.join(cacheRoot, 'audio'),
  };
}
