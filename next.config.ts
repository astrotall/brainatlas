import type { NextConfig } from 'next';
import { PHASE_DEVELOPMENT_SERVER } from 'next/constants';
import {
  buildCacheHeaderRules,
  buildSecurityHeaderRule,
  LEGACY_REWRITES,
} from './src/shared/config';

const nextConfig = (phase: string): NextConfig => ({
  poweredByHeader: false,
  headers: () =>
    Promise.resolve([
      buildSecurityHeaderRule({ isDevelopment: phase === PHASE_DEVELOPMENT_SERVER }),
      ...buildCacheHeaderRules(),
    ]),
  rewrites: () =>
    Promise.resolve(LEGACY_REWRITES.map(({ source, destination }) => ({ source, destination }))),
});

export default nextConfig;
