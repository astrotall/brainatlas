import type { NextConfig } from 'next';
import { LEGACY_REWRITES } from './src/shared/config';

const nextConfig: NextConfig = {
  rewrites: () =>
    Promise.resolve(LEGACY_REWRITES.map(({ source, destination }) => ({ source, destination }))),
};

export default nextConfig;
