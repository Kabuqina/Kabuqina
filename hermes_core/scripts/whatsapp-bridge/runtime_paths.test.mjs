import assert from 'node:assert/strict';
import path from 'node:path';
import test from 'node:test';

import { resolveRuntimePaths } from './runtime_paths.js';

test('active KABUQINA_HOME owns new session and media cache paths', () => {
  const root = path.resolve('C:/profile/whatsapp');
  const paths = resolveRuntimePaths('', '', { KABUQINA_HOME: root });
  assert.equal(paths.sessionDir, path.join(root, 'platforms', 'whatsapp', 'session'));
  assert.equal(paths.imageCacheDir, path.join(root, 'cache', 'images'));
  assert.equal(paths.documentCacheDir, path.join(root, 'cache', 'documents'));
  assert.equal(paths.audioCacheDir, path.join(root, 'cache', 'audio'));
});

test('explicit adapter paths override environment defaults', () => {
  const session = path.resolve('D:/sessions/wa');
  const cache = path.resolve('D:/cache');
  const paths = resolveRuntimePaths(session, cache, { KABUQINA_HOME: 'C:/ignored' });
  assert.equal(paths.sessionDir, session);
  assert.equal(paths.imageCacheDir, path.join(cache, 'images'));
});
