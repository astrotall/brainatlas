import { PUBLIC_FILE, toPublicPath } from './public-files';

export const ROUTE = {
  ROOT: '/',
  HOME: '/index',
  WORKBOOK: '/workbook',
  KIRA: '/kira',
  ATLAS: '/mozg-3d-atlas-2',
} as const;

export interface LegacyRewrite {
  readonly source: string;
  readonly destination: string;
}

export const LEGACY_REWRITES: readonly LegacyRewrite[] = [
  { source: ROUTE.ROOT, destination: toPublicPath(PUBLIC_FILE.HOME) },
  { source: ROUTE.HOME, destination: toPublicPath(PUBLIC_FILE.HOME) },
  { source: ROUTE.WORKBOOK, destination: toPublicPath(PUBLIC_FILE.WORKBOOK) },
  { source: ROUTE.KIRA, destination: toPublicPath(PUBLIC_FILE.KIRA) },
  { source: ROUTE.ATLAS, destination: toPublicPath(PUBLIC_FILE.ATLAS) },
];
