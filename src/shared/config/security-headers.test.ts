import { PHASE_DEVELOPMENT_SERVER, PHASE_PRODUCTION_BUILD, PHASE_TEST } from 'next/constants';
import { unstable_getResponseFromNextConfig } from 'next/experimental/testing/server';
import { describe, expect, it } from 'vitest';
import nextConfig from '../../../next.config';
import { ALL_PATHS } from './security-headers';

const BASE_URL = 'http://localhost';

const REQUIRED_HEADERS: readonly string[] = [
  'Content-Security-Policy',
  'X-Frame-Options',
  'X-Content-Type-Options',
  'Referrer-Policy',
  'Permissions-Policy',
  'Strict-Transport-Security',
];

const DENIED_FEATURES: readonly string[] = [
  'accelerometer',
  'autoplay',
  'bluetooth',
  'camera',
  'clipboard-read',
  'clipboard-write',
  'display-capture',
  'encrypted-media',
  'geolocation',
  'gyroscope',
  'hid',
  'magnetometer',
  'microphone',
  'midi',
  'payment',
  'picture-in-picture',
  'publickey-credentials-get',
  'screen-wake-lock',
  'serial',
  'usb',
  'xr-spatial-tracking',
];

const ALLOWED_SOURCES: readonly string[] = [
  "'none'",
  "'self'",
  "'unsafe-inline'",
  "'unsafe-eval'",
  'data:',
];

const REQUEST_URLS: readonly string[] = [
  '/',
  '/index',
  '/index.html',
  '/workbook',
  '/workbook/',
  '/workbook.html',
  '/WORKBOOK',
  '/kira',
  '/kira.html',
  '/mozg-3d-atlas-2',
  '/mozg-3d-atlas-2.html?embed=1&mode=p:memory&v=5',
  '/atlas-preview.jpg',
  '/ATLAS-PREVIEW.JPG',
  '/LICENSE-freesurfer.txt',
  '/LICENSE-atlas-data.txt',
  '/_next/static/chunks/app.css',
  '/api',
  '/api/health',
  '/api/docs',
  '/api/reviews?lang=ru',
  '/api/index?__path=reviews',
  '/missing',
  '/missing/deeply/nested.html',
  '/README.md',
  '/.env',
  '/%D0%BC%D0%BE%D0%B7%D0%B3',
  '/a%20b?x=%3Cscript%3E',
];

const loadHeaderRules = async (phase: string) => (await nextConfig(phase).headers?.()) ?? [];

const loadSecurityHeaders = async (phase: string): Promise<ReadonlyMap<string, string>> => {
  const rules = await loadHeaderRules(phase);
  const catchAll = rules.filter((rule) => rule.source === ALL_PATHS);

  return new Map(catchAll.flatMap((rule) => rule.headers.map(({ key, value }) => [key, value])));
};

const directiveEntries = async (phase: string): Promise<[string, string[]][]> => {
  const policy = (await loadSecurityHeaders(phase)).get('Content-Security-Policy') ?? '';

  return policy.split(';').map((directive) => {
    const [name = '', ...sources] = directive.trim().split(/\s+/);

    return [name, sources];
  });
};

const loadDirectives = async (phase: string): Promise<ReadonlyMap<string, string[]>> =>
  new Map(await directiveEntries(phase));

const loadFeatures = async (): Promise<ReadonlyMap<string, string>> => {
  const policy =
    (await loadSecurityHeaders(PHASE_PRODUCTION_BUILD)).get('Permissions-Policy') ?? '';

  return new Map(
    policy.split(',').map((entry) => {
      const [feature = '', allowList = ''] = entry.trim().split('=');

      return [feature, allowList];
    }),
  );
};

describe('security headers', () => {
  it.each(REQUIRED_HEADERS)('sends %s on every path', async (header) => {
    expect((await loadSecurityHeaders(PHASE_PRODUCTION_BUILD)).get(header)).toBeTruthy();
  });

  it.each(REQUEST_URLS)('matches every required header for %s', async (url) => {
    const response = await unstable_getResponseFromNextConfig({
      url: `${BASE_URL}${url}`,
      nextConfig,
    });

    expect(REQUIRED_HEADERS.filter((header) => !response.headers.has(header))).toEqual([]);
  });

  it('defines each security header only in the catch-all rule, so no later rule weakens it', async () => {
    const rules = await loadHeaderRules(PHASE_PRODUCTION_BUILD);
    const narrowKeys = rules
      .filter((rule) => rule.source !== ALL_PATHS)
      .flatMap((rule) => rule.headers.map(({ key }) => key.toLowerCase()));
    const requiredKeys = REQUIRED_HEADERS.map((header) => header.toLowerCase());

    expect(narrowKeys.filter((key) => requiredKeys.includes(key))).toEqual([]);
    expect(rules.filter((rule) => rule.source === ALL_PATHS)).toHaveLength(1);
  });

  it('does not advertise the framework', () => {
    expect(nextConfig(PHASE_PRODUCTION_BUILD).poweredByHeader).toBe(false);
  });

  it('keeps HSTS long and limited to this host', async () => {
    const hsts = (await loadSecurityHeaders(PHASE_PRODUCTION_BUILD)).get(
      'Strict-Transport-Security',
    );

    expect(hsts).toBe('max-age=31536000');
  });

  it('forbids framing by other origins, sniffing and referrers', async () => {
    const headers = await loadSecurityHeaders(PHASE_PRODUCTION_BUILD);

    expect(headers.get('X-Frame-Options')).toBe('SAMEORIGIN');
    expect(headers.get('X-Content-Type-Options')).toBe('nosniff');
    expect(headers.get('Referrer-Policy')).toBe('no-referrer');
  });

  it('allows only fullscreen, and only for this origin', async () => {
    const features = await loadFeatures();
    const allowed = [...features].filter(([, allowList]) => allowList !== '()');

    expect(allowed).toEqual([['fullscreen', '(self)']]);
  });

  it.each(DENIED_FEATURES)('denies %s', async (feature) => {
    expect((await loadFeatures()).get(feature)).toBe('()');
  });
});

describe('content security policy', () => {
  it('names each directive once, because browsers ignore a repeated one', async () => {
    const names = (await directiveEntries(PHASE_PRODUCTION_BUILD)).map(([name]) => name);

    expect(new Set(names).size).toBe(names.length);
  });

  const EXPECTED_DIRECTIVES: ReadonlyArray<readonly [string, readonly string[]]> = [
    ['default-src', ["'none'"]],
    ['script-src', ["'self'", "'unsafe-inline'"]],
    ['style-src', ["'self'", "'unsafe-inline'"]],
    ['img-src', ["'self'", 'data:']],
    ['font-src', ["'self'", 'data:']],
    ['connect-src', ["'self'"]],
    ['frame-src', ["'self'"]],
    ['object-src', ["'none'"]],
    ['base-uri', ["'none'"]],
    ['form-action', ["'self'"]],
    ['frame-ancestors', ["'self'"]],
  ];

  it('declares no directive beyond the expected ones', async () => {
    const names = [...(await loadDirectives(PHASE_PRODUCTION_BUILD)).keys()];

    expect(names).toEqual(EXPECTED_DIRECTIVES.map(([name]) => name));
  });

  it.each(EXPECTED_DIRECTIVES)('sets %s to exactly %j', async (name, sources) => {
    expect((await loadDirectives(PHASE_PRODUCTION_BUILD)).get(name)).toEqual(sources);
  });

  it.each([PHASE_PRODUCTION_BUILD, PHASE_DEVELOPMENT_SERVER])(
    'allows no external origin, scheme wildcard or `*` in %s',
    async (phase) => {
      const sources = [...(await loadDirectives(phase)).values()].flat();

      expect(sources.filter((source) => !ALLOWED_SOURCES.includes(source))).toEqual([]);
      expect(sources.join(' ')).not.toMatch(/\*|cdnjs|https?:|wss?:|blob:/);
    },
  );

  it.each([PHASE_PRODUCTION_BUILD, PHASE_TEST, 'phase-production-server', 'phase-export', ''])(
    "never allows 'unsafe-eval' in %j",
    async (phase) => {
      const sources = [...(await loadDirectives(phase)).values()].flat();

      expect(sources).not.toContain("'unsafe-eval'");
    },
  );

  it("adds 'unsafe-eval' to script-src, and nothing else, under next dev", async () => {
    const production = await loadDirectives(PHASE_PRODUCTION_BUILD);
    const development = await loadDirectives(PHASE_DEVELOPMENT_SERVER);

    expect([...development]).toEqual(
      [...production].map(([name, sources]) => [
        name,
        name === 'script-src' ? [...sources, "'unsafe-eval'"] : sources,
      ]),
    );
  });
});
