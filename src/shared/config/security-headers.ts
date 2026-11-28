export interface ResponseHeader {
  key: string;
  value: string;
}

export interface HeaderRule {
  source: string;
  headers: ResponseHeader[];
}

export interface SecurityHeadersOptions {
  readonly isDevelopment: boolean;
}

export const ALL_PATHS = '/:path*';

const CSP_SOURCE = {
  NONE: "'none'",
  SELF: "'self'",
  UNSAFE_INLINE: "'unsafe-inline'",
  UNSAFE_EVAL: "'unsafe-eval'",
  DATA: 'data:',
} as const;

type CspSource = (typeof CSP_SOURCE)[keyof typeof CSP_SOURCE];

type CspDirective = readonly [name: string, sources: readonly CspSource[]];

const HSTS_MAX_AGE_SECONDS = 31_536_000;

const ALLOWED_FEATURES: readonly string[] = ['fullscreen'];

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

const scriptSources = ({ isDevelopment }: SecurityHeadersOptions): readonly CspSource[] => {
  const sources = [CSP_SOURCE.SELF, CSP_SOURCE.UNSAFE_INLINE];

  return isDevelopment ? [...sources, CSP_SOURCE.UNSAFE_EVAL] : sources;
};

const contentSecurityPolicy = (options: SecurityHeadersOptions): string => {
  const directives: readonly CspDirective[] = [
    ['default-src', [CSP_SOURCE.NONE]],
    ['script-src', scriptSources(options)],
    ['style-src', [CSP_SOURCE.SELF, CSP_SOURCE.UNSAFE_INLINE]],
    ['img-src', [CSP_SOURCE.SELF, CSP_SOURCE.DATA]],
    ['font-src', [CSP_SOURCE.SELF, CSP_SOURCE.DATA]],
    ['connect-src', [CSP_SOURCE.SELF]],
    ['frame-src', [CSP_SOURCE.SELF]],
    ['object-src', [CSP_SOURCE.NONE]],
    ['base-uri', [CSP_SOURCE.NONE]],
    ['form-action', [CSP_SOURCE.SELF]],
    ['frame-ancestors', [CSP_SOURCE.SELF]],
  ];

  return directives.map(([name, sources]) => [name, ...sources].join(' ')).join('; ');
};

const permissionsPolicy = (): string =>
  [
    ...ALLOWED_FEATURES.map((feature) => `${feature}=(self)`),
    ...DENIED_FEATURES.map((feature) => `${feature}=()`),
  ].join(', ');

export const buildSecurityHeaderRule = (options: SecurityHeadersOptions): HeaderRule => ({
  source: ALL_PATHS,
  headers: [
    { key: 'Content-Security-Policy', value: contentSecurityPolicy(options) },
    { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'Referrer-Policy', value: 'no-referrer' },
    { key: 'Permissions-Policy', value: permissionsPolicy() },
    { key: 'Strict-Transport-Security', value: `max-age=${HSTS_MAX_AGE_SECONDS}` },
  ],
});
