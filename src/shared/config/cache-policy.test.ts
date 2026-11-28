import { PHASE_PRODUCTION_BUILD } from 'next/constants';
import { unstable_getResponseFromNextConfig } from 'next/experimental/testing/server';
import { describe, expect, it } from 'vitest';
import nextConfig from '../../../next.config';
import { buildCacheHeaderRules, CACHE_CONTROL, PUBLIC_FILE_CACHE } from './cache-policy';
import type { CacheControl } from './cache-policy';
import { PUBLIC_FILE, PUBLIC_FILES, toPublicPath } from './public-files';
import type { PublicFile } from './public-files';
import { LEGACY_REWRITES } from './routes';
import { ALL_PATHS } from './security-headers';

const BASE_URL = 'http://localhost';

const PAGES: readonly PublicFile[] = [PUBLIC_FILE.HOME, PUBLIC_FILE.WORKBOOK, PUBLIC_FILE.KIRA];

const SERVED_URLS: ReadonlyArray<readonly [string, CacheControl]> = [
  ['/', CACHE_CONTROL.REVALIDATE],
  ['/?lang=en', CACHE_CONTROL.REVALIDATE],
  ['/index', CACHE_CONTROL.REVALIDATE],
  ['/index.html', CACHE_CONTROL.REVALIDATE],
  ['/workbook', CACHE_CONTROL.REVALIDATE],
  ['/workbook/', CACHE_CONTROL.REVALIDATE],
  ['/workbook.html', CACHE_CONTROL.REVALIDATE],
  ['/kira', CACHE_CONTROL.REVALIDATE],
  ['/kira.html', CACHE_CONTROL.REVALIDATE],
  ['/mozg-3d-atlas-2', CACHE_CONTROL.MODERATE],
  ['/mozg-3d-atlas-2?embed=1&mode=p:memory', CACHE_CONTROL.MODERATE],
  ['/mozg-3d-atlas-2.html', CACHE_CONTROL.MODERATE],
  ['/mozg-3d-atlas-2.html?embed=1&mode=p:memory&v=5', CACHE_CONTROL.MODERATE],
  ['/atlas-preview.jpg', CACHE_CONTROL.MODERATE],
  ['/LICENSE-freesurfer.txt', CACHE_CONTROL.MODERATE],
  ['/LICENSE-atlas-data.txt', CACHE_CONTROL.MODERATE],
];

const UNRULED_URLS: readonly string[] = [
  '/_next/static/chunks/app.css',
  '/_next/static/media/atlas-preview.jpg',
  '/_next/image?url=%2Fatlas-preview.jpg',
  '/api/health',
  '/api/docs',
  '/api/atlas-preview.jpg',
  '/missing',
  '/nested/workbook',
  '/workbook/extra',
  '/workbook.htm',
  '/workbook.htmlx',
  '/workbookXhtml',
  '/atlas-preview_jpg',
  '/mozg-3d-atlas',
];

const cacheControlOf = async (url: string): Promise<string | null> => {
  const response = await unstable_getResponseFromNextConfig({
    url: `${BASE_URL}${url}`,
    nextConfig,
  });

  return response.headers.get('Cache-Control');
};

describe('cache policy', () => {
  it('is part of the real Next config', async () => {
    const rules = (await nextConfig(PHASE_PRODUCTION_BUILD).headers?.()) ?? [];

    expect(rules.filter((rule) => rule.source !== ALL_PATHS)).toEqual(buildCacheHeaderRules());
  });

  it('covers every public file and every short URL exactly once', () => {
    const sources = buildCacheHeaderRules().map((rule) => rule.source.toLowerCase());
    const served = [
      ...PUBLIC_FILES.map(toPublicPath),
      ...LEGACY_REWRITES.map(({ source }) => source),
    ].map((path) => path.toLowerCase());

    expect([...sources].sort()).toEqual([...served].sort());
    expect(new Set(sources).size).toBe(sources.length);
  });

  it('uses only literal sources, so two cache rules can never match one path', () => {
    for (const { source } of buildCacheHeaderRules()) {
      expect(source).toMatch(/^\/[A-Za-z0-9._-]*$/);
    }
  });

  it.each(LEGACY_REWRITES)(
    'gives $source the same policy as $destination',
    async ({ source, destination }) => {
      expect(await cacheControlOf(source)).toBe(await cacheControlOf(destination));
    },
  );

  it.each(SERVED_URLS)('sends %s with "%s"', async (url, policy) => {
    expect(await cacheControlOf(url)).toBe(policy);
  });

  it.each(UNRULED_URLS)('leaves %s to Next or the function', async (url) => {
    expect(await cacheControlOf(url)).toBeNull();
  });

  it.each(PUBLIC_FILES)('never marks the unhashed %s immutable', (file) => {
    expect(PUBLIC_FILE_CACHE[file]).not.toContain('immutable');
  });

  it.each(PUBLIC_FILES.filter((file) => !PAGES.includes(file)))(
    'gives %s the moderate policy',
    (file) => {
      expect(PUBLIC_FILE_CACHE[file]).toBe(CACHE_CONTROL.MODERATE);
    },
  );

  it.each(PAGES)('makes browsers revalidate %s', (file) => {
    expect(PUBLIC_FILE_CACHE[file]).toBe(CACHE_CONTROL.REVALIDATE);
  });

  it('keeps the moderate policy fresh for an hour and stale for at most a day more', () => {
    expect(CACHE_CONTROL.MODERATE).toBe('public, max-age=3600, stale-while-revalidate=86400');
  });
});
