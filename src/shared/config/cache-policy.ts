import { PUBLIC_FILE, PUBLIC_FILES, toPublicPath } from './public-files';
import type { PublicFile } from './public-files';
import { LEGACY_REWRITES } from './routes';
import type { HeaderRule } from './security-headers';

export const CACHE_CONTROL = {
  REVALIDATE: 'public, max-age=0, must-revalidate',
  MODERATE: 'public, max-age=3600, stale-while-revalidate=86400',
} as const;

export type CacheControl = (typeof CACHE_CONTROL)[keyof typeof CACHE_CONTROL];

export const PUBLIC_FILE_CACHE: Readonly<Record<PublicFile, CacheControl>> = {
  [PUBLIC_FILE.HOME]: CACHE_CONTROL.REVALIDATE,
  [PUBLIC_FILE.WORKBOOK]: CACHE_CONTROL.REVALIDATE,
  [PUBLIC_FILE.KIRA]: CACHE_CONTROL.REVALIDATE,
  [PUBLIC_FILE.ATLAS]: CACHE_CONTROL.MODERATE,
  [PUBLIC_FILE.ATLAS_PREVIEW]: CACHE_CONTROL.MODERATE,
  [PUBLIC_FILE.FREESURFER_LICENSE]: CACHE_CONTROL.MODERATE,
  [PUBLIC_FILE.ATLAS_DATA_LICENSE]: CACHE_CONTROL.MODERATE,
};

const servedPaths = (file: PublicFile): string[] => {
  const filePath = toPublicPath(file);
  const rewritten = LEGACY_REWRITES.filter(({ destination }) => destination === filePath);

  return [filePath, ...rewritten.map(({ source }) => source)];
};

export const buildCacheHeaderRules = (): HeaderRule[] =>
  PUBLIC_FILES.flatMap((file) =>
    servedPaths(file).map((source) => ({
      source,
      headers: [{ key: 'Cache-Control', value: PUBLIC_FILE_CACHE[file] }],
    })),
  );
