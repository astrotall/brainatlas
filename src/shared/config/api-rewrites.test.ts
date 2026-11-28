import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { PHASE_DEVELOPMENT_SERVER, PHASE_PRODUCTION_BUILD, PHASE_TEST } from 'next/constants';
import {
  getRewrittenUrl,
  unstable_getResponseFromNextConfig,
} from 'next/experimental/testing/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import nextConfig from '../../../next.config';
import {
  API_FORWARDED_PATH_PARAM,
  API_FUNCTION_PATH,
  API_PREFIX,
  API_REWRITES,
  LEGACY_REWRITES,
  LOCAL_API_ORIGIN,
  LOCAL_API_REWRITES,
} from './routes';

const BASE_URL = 'http://localhost';

const DEPLOYED_PHASES: readonly string[] = [
  PHASE_PRODUCTION_BUILD,
  'phase-production-server',
  'phase-export',
  PHASE_TEST,
  '',
];

const NODE_ENVIRONMENTS: readonly string[] = ['production', 'development', 'test', ''];

const DEPLOYED_CASES = DEPLOYED_PHASES.flatMap((phase) =>
  NODE_ENVIRONMENTS.map((environment) => [phase, environment] as const),
);

const FUNCTION_URL = `${BASE_URL}${API_FUNCTION_PATH}`;

const REWRITTEN: ReadonlyArray<readonly [string, string]> = [
  ['/api', `${FUNCTION_URL}?__path=`],
  ['/api/health', `${FUNCTION_URL}?__path=health`],
  ['/api/openapi.json', `${FUNCTION_URL}?__path=openapi.json`],
  ['/api/docs', `${FUNCTION_URL}?__path=docs`],
  ['/api/reviews?lang=ru&limit=5', `${FUNCTION_URL}?lang=ru&limit=5&__path=reviews`],
  ['/api/unknown/deeply/nested', `${FUNCTION_URL}?__path=unknown%2Fdeeply%2Fnested`],
  ['/api/health.py', `${FUNCTION_URL}?__path=health.py`],
  ['/api/reviews?__path=health', `${FUNCTION_URL}?__path=reviews`],
];

const NOT_REWRITTEN_TO_THE_API: readonly string[] = [
  '/apix',
  '/apis/health',
  '/nested/api/health',
  '/missing',
];

const rewrittenUrl = async (url: string): Promise<string | null> =>
  getRewrittenUrl(
    await unstable_getResponseFromNextConfig({ url: `${BASE_URL}${url}`, nextConfig }),
  );

const loadConfig = async (phase: string) => {
  const config = nextConfig(phase);

  return { rewrites: await config.rewrites?.(), headers: await config.headers?.() };
};

const readSource = (...segments: string[]): Promise<string> =>
  readFile(join(process.cwd(), ...segments), 'utf8');

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('deployed API routing', () => {
  it.each(REWRITTEN)('sends %s to the single function', async (url, destination) => {
    expect(await rewrittenUrl(url)).toBe(destination);
  });

  it.each(NOT_REWRITTEN_TO_THE_API)('leaves %s alone', async (url) => {
    expect(await rewrittenUrl(url)).toBeNull();
  });

  it('names a function file that exists, and no other Python file that would become one', async () => {
    const files = await readdir(join(process.cwd(), 'api'), { recursive: true });

    expect(files.filter((file) => file.endsWith('.py'))).toEqual([
      `${API_FUNCTION_PATH.slice(API_PREFIX.length + 1)}.py`,
    ]);
  });

  it('agrees with the backend on the prefix, the parameter and the function path', async () => {
    const source = await readSource(
      'backend',
      'src',
      'neuroctivity',
      'transport',
      'forwarded_path.py',
    );

    expect(source).toContain(`API_PREFIX = "${API_PREFIX}"`);
    expect(source).toContain(`FORWARDED_PATH_PARAM = "${API_FORWARDED_PATH_PARAM}"`);
    expect(source).toContain(`"${API_FUNCTION_PATH}"`);
  });
});

describe('local API proxy', () => {
  it('replaces the function rewrites under next dev with NODE_ENV=development', async () => {
    vi.stubEnv('NODE_ENV', 'development');

    const { rewrites } = await loadConfig(PHASE_DEVELOPMENT_SERVER);

    expect(rewrites).toEqual([...LEGACY_REWRITES, ...LOCAL_API_REWRITES]);
  });

  it('points at the address that make run listens on', () => {
    expect(LOCAL_API_ORIGIN).toBe('http://127.0.0.1:8000');
    expect(LOCAL_API_REWRITES).toEqual([
      { source: '/api/:path*', destination: 'http://127.0.0.1:8000/api/:path*' },
    ]);
  });

  it.each(['/api', '/api/health', '/api/reviews?lang=ru&limit=5'])(
    'forwards %s to the local API with its path and query',
    async (url) => {
      vi.stubEnv('NODE_ENV', 'development');
      const response = await unstable_getResponseFromNextConfig({
        url: `${BASE_URL}${url}`,
        nextConfig: () => nextConfig(PHASE_DEVELOPMENT_SERVER),
      });

      const target = new URL(getRewrittenUrl(response) ?? '');

      expect(target.hostname).toBe(new URL(LOCAL_API_ORIGIN).hostname);
      expect(`${target.pathname}${target.search}`).toBe(url);
    },
  );

  it.each(['production', 'test', ''])(
    'stays off under next dev when NODE_ENV is %j',
    async (environment) => {
      vi.stubEnv('NODE_ENV', environment);

      const { rewrites } = await loadConfig(PHASE_DEVELOPMENT_SERVER);

      expect(rewrites).toEqual([...LEGACY_REWRITES, ...API_REWRITES]);
    },
  );

  it.each(DEPLOYED_CASES)(
    'never reaches phase %j, whatever NODE_ENV %j says',
    async (phase, environment) => {
      vi.stubEnv('NODE_ENV', environment);

      const { rewrites } = await loadConfig(phase);

      expect(rewrites).toEqual([...LEGACY_REWRITES, ...API_REWRITES]);
      expect(JSON.stringify(rewrites)).not.toMatch(/:\/\/|127\.0\.0\.1|localhost|8000/);
    },
  );

  it.each(NODE_ENVIRONMENTS)(
    'leaves the deployed headers and caching untouched with NODE_ENV %j',
    async (environment) => {
      vi.stubEnv('NODE_ENV', 'production');
      const deployed = await loadConfig(PHASE_PRODUCTION_BUILD);
      vi.stubEnv('NODE_ENV', environment);

      expect(await loadConfig(PHASE_PRODUCTION_BUILD)).toEqual(deployed);
    },
  );

  it('changes nothing but the API rewrites between next dev with and without it', async () => {
    vi.stubEnv('NODE_ENV', 'development');
    const withProxy = await loadConfig(PHASE_DEVELOPMENT_SERVER);
    vi.stubEnv('NODE_ENV', 'production');
    const withoutProxy = await loadConfig(PHASE_DEVELOPMENT_SERVER);

    expect(withProxy.headers).toEqual(withoutProxy.headers);
    expect(withProxy.rewrites).not.toEqual(withoutProxy.rewrites);
  });
});
