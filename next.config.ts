import type { NextConfig } from 'next';
import { PHASE_DEVELOPMENT_SERVER } from 'next/constants';
import { buildCacheHeaderRules, buildRewrites, buildSecurityHeaderRule } from './src/shared/config';

const nextConfig = (phase: string): NextConfig => {
  const isDevelopmentServer = phase === PHASE_DEVELOPMENT_SERVER;
  const isLocalDevelopment = isDevelopmentServer && process.env.NODE_ENV === 'development';

  return {
    poweredByHeader: false,
    headers: () =>
      Promise.resolve([
        buildSecurityHeaderRule({ isDevelopment: isDevelopmentServer }),
        ...buildCacheHeaderRules(),
      ]),
    rewrites: () => Promise.resolve(buildRewrites({ isLocalDevelopment })),
  };
};

export default nextConfig;
