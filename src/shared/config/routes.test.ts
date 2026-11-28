import { PHASE_PRODUCTION_BUILD } from 'next/constants';
import { describe, expect, it } from 'vitest';
import nextConfig from '../../../next.config';
import { PUBLIC_FILE, PUBLIC_FILES, toPublicPath } from './public-files';
import type { PublicFile } from './public-files';
import { API_REWRITES, LEGACY_REWRITES } from './routes';
import type { LegacyRewrite } from './routes';

const BASE_URL = 'http://localhost';

const LEGACY_URLS: ReadonlyArray<readonly [string, PublicFile]> = [
  ['/', PUBLIC_FILE.HOME],
  ['/index.html', PUBLIC_FILE.HOME],
  ['/index', PUBLIC_FILE.HOME],
  ['/workbook.html', PUBLIC_FILE.WORKBOOK],
  ['/workbook', PUBLIC_FILE.WORKBOOK],
  ['/kira.html', PUBLIC_FILE.KIRA],
  ['/kira', PUBLIC_FILE.KIRA],
  ['/mozg-3d-atlas-2.html', PUBLIC_FILE.ATLAS],
  ['/mozg-3d-atlas-2', PUBLIC_FILE.ATLAS],
  ['/mozg-3d-atlas-2.html?mode=p:memory&embed=1', PUBLIC_FILE.ATLAS],
  ['/mozg-3d-atlas-2.html?mode=c:dopamine', PUBLIC_FILE.ATLAS],
  ['/mozg-3d-atlas-2?embed=1&mode=p:memory', PUBLIC_FILE.ATLAS],
  ['/mozg-3d-atlas-2?mode=c:dopamine', PUBLIC_FILE.ATLAS],
  ['/index?lang=en', PUBLIC_FILE.HOME],
  ['/atlas-preview.jpg', PUBLIC_FILE.ATLAS_PREVIEW],
  ['/LICENSE-freesurfer.txt', PUBLIC_FILE.FREESURFER_LICENSE],
  ['/LICENSE-atlas-data.txt', PUBLIC_FILE.ATLAS_DATA_LICENSE],
];

const UNSERVED_URLS: readonly string[] = [
  '/README.md',
  '/README',
  '/package.json',
  '/netlify.toml',
  '/_headers',
  '/.account-data',
  '/.idea/misc.xml',
  '/atlas',
  '/mozg',
  '/api/health',
];

const loadRewrites = async (): Promise<readonly LegacyRewrite[]> => {
  const rewrites = await nextConfig(PHASE_PRODUCTION_BUILD).rewrites?.();

  if (!Array.isArray(rewrites)) {
    throw new TypeError('next.config.ts must return a flat rewrite list');
  }

  return rewrites;
};

const servedFile = (url: string, rewrites: readonly LegacyRewrite[]): PublicFile | undefined => {
  const { pathname } = new URL(url, BASE_URL);
  const target = rewrites.find((rewrite) => rewrite.source === pathname)?.destination ?? pathname;

  return PUBLIC_FILES.find((file) => toPublicPath(file) === target);
};

describe('legacy URLs', () => {
  it('registers exactly the rewrites defined in shared config', async () => {
    expect(await loadRewrites()).toEqual([...LEGACY_REWRITES, ...API_REWRITES]);
  });

  it.each(LEGACY_URLS)('serves %s from %s', async (url, file) => {
    expect(servedFile(url, await loadRewrites())).toBe(file);
  });

  it.each(UNSERVED_URLS)('serves nothing for %s', async (url) => {
    expect(servedFile(url, await loadRewrites())).toBeUndefined();
  });

  it.each(LEGACY_REWRITES)(
    'rewrites $source with a literal path so the original query string is forwarded',
    ({ source, destination }) => {
      expect(source).toMatch(/^\/[a-z0-9-]*$/);
      expect(destination).not.toContain('?');
      expect(PUBLIC_FILES.map(toPublicPath)).toContain(destination);
      expect(PUBLIC_FILES.map(toPublicPath)).not.toContain(source);
    },
  );
});
