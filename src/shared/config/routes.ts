import { PUBLIC_FILE, toPublicPath } from './public-files';

export const ROUTE = {
  ROOT: '/',
  HOME: '/index',
  WORKBOOK: '/workbook',
  KIRA: '/kira',
  ATLAS: '/mozg-3d-atlas-2',
} as const;

export interface Rewrite {
  readonly source: string;
  readonly destination: string;
}

export type LegacyRewrite = Rewrite;

export const LEGACY_REWRITES: readonly LegacyRewrite[] = [
  { source: ROUTE.ROOT, destination: toPublicPath(PUBLIC_FILE.HOME) },
  { source: ROUTE.HOME, destination: toPublicPath(PUBLIC_FILE.HOME) },
  { source: ROUTE.WORKBOOK, destination: toPublicPath(PUBLIC_FILE.WORKBOOK) },
  { source: ROUTE.KIRA, destination: toPublicPath(PUBLIC_FILE.KIRA) },
  { source: ROUTE.ATLAS, destination: toPublicPath(PUBLIC_FILE.ATLAS) },
];

export const API_PREFIX = '/api';

export const API_FUNCTION_PATH = `${API_PREFIX}/index`;

export const API_FORWARDED_PATH_PARAM = '__path';

export const API_REWRITE_PARAM = '__api_path';

export const LOCAL_API_ORIGIN = 'http://127.0.0.1:8000';

const API_ANY_PATH = `${API_PREFIX}/:path*`;

const API_REWRITE_SOURCE = `${API_PREFIX}/:${API_REWRITE_PARAM}*`;

const toApiFunction = (forwardedPath: string): string =>
  `${API_FUNCTION_PATH}?${API_FORWARDED_PATH_PARAM}=${forwardedPath}`;

export const API_REWRITES: readonly Rewrite[] = [
  { source: API_PREFIX, destination: toApiFunction('') },
  { source: API_REWRITE_SOURCE, destination: toApiFunction(`:${API_REWRITE_PARAM}*`) },
];

export const LOCAL_API_REWRITES: readonly Rewrite[] = [
  { source: API_ANY_PATH, destination: `${LOCAL_API_ORIGIN}${API_ANY_PATH}` },
];

export interface RewriteOptions {
  readonly isLocalDevelopment: boolean;
}

export const buildRewrites = ({ isLocalDevelopment }: RewriteOptions): Rewrite[] => [
  ...LEGACY_REWRITES,
  ...(isLocalDevelopment ? LOCAL_API_REWRITES : API_REWRITES),
];
