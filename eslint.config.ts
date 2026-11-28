import nextPlugin from '@next/eslint-plugin-next';
import boundaries from 'eslint-plugin-boundaries';
import reactHooks from 'eslint-plugin-react-hooks';
import type { Linter } from 'eslint';
import { defineConfig, globalIgnores } from 'eslint/config';
import tseslint from 'typescript-eslint';

const LAYERS = ['app', 'screens', 'widgets', 'features', 'entities', 'shared'] as const;

type Layer = (typeof LAYERS)[number];

const allowedBelow = (layer: Layer): Layer[] => LAYERS.slice(LAYERS.indexOf(layer) + 1);

const PUBLIC_API = 'index.ts';

const publicApiOf = (type: string) => ({ to: { element: { type, fileInternalPath: PUBLIC_API } } });

const policy = (from: string, allowed: readonly string[]) => ({
  from: { element: { type: from } },
  allow: allowed.map(publicApiOf),
});

const strictRules: Linter.RulesRecord = {
  '@typescript-eslint/no-explicit-any': 'error',
  '@typescript-eslint/no-non-null-assertion': 'error',
  '@typescript-eslint/consistent-type-imports': 'error',
  '@typescript-eslint/no-unused-vars': [
    'error',
    {
      argsIgnorePattern: '^_',
      varsIgnorePattern: '^_',
      caughtErrorsIgnorePattern: '^_',
      ignoreRestSiblings: true,
    },
  ],
  complexity: ['error', 12],
  'max-params': ['error', 4],
  'max-depth': ['error', 4],
  'max-nested-callbacks': ['error', 3],
  'max-lines': ['error', { max: 300, skipBlankLines: true, skipComments: true }],
  'max-lines-per-function': ['error', { max: 80, skipBlankLines: true, skipComments: true }],
};

const storeSelectorRules: Linter.RulesRecord = {
  'no-restricted-syntax': [
    'error',
    {
      selector:
        "CallExpression[callee.type='Identifier'][callee.name=/^use(?!SyncExternalStore).+Store$/][arguments.length=0]",
      message:
        'Select from a store with a narrow selector: useXStore((s) => s.field). Reading the whole store re-renders on every unrelated change.',
    },
    {
      selector:
        "CallExpression[callee.type='Identifier'][callee.name=/^use(?!SyncExternalStore).+Store$/] > ArrowFunctionExpression[body.type='ObjectExpression']",
      message:
        'A store selector that returns an object literal allocates a new object every render. Wrap it in useShallow, or select each field separately.',
    },
  ],
};

export default defineConfig(
  globalIgnores([
    '.next/**',
    'out/**',
    'node_modules/**',
    'public/**',
    'next-env.d.ts',
    '.venv/**',
    'src/shared/api/generated/**',
  ]),
  ...tseslint.configs.recommended,
  nextPlugin.configs['core-web-vitals'],
  reactHooks.configs.flat.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    rules: { ...strictRules, ...storeSelectorRules },
  },
  {
    files: ['src/**/*.{ts,tsx}', 'app/**/*.{ts,tsx}'],
    plugins: { boundaries },
    settings: {
      'import/resolver': { typescript: { project: './tsconfig.json' } },
      'boundaries/include': ['src/**/*', 'app/**/*'],
      'boundaries/elements': [
        { type: 'routes', pattern: 'app', partialMatch: false },
        { type: 'app', pattern: 'src/app', partialMatch: false },
        { type: 'screens', pattern: 'src/screens/*', capture: ['slice'], partialMatch: false },
        { type: 'widgets', pattern: 'src/widgets/*', capture: ['slice'], partialMatch: false },
        { type: 'features', pattern: 'src/features/*', capture: ['slice'], partialMatch: false },
        { type: 'entities', pattern: 'src/entities/*', capture: ['slice'], partialMatch: false },
        { type: 'shared', pattern: 'src/shared/*', capture: ['segment'], partialMatch: false },
      ],
    },
    rules: {
      'boundaries/dependencies': [
        'error',
        {
          default: 'disallow',
          policies: [
            policy('routes', ['app', 'screens']),
            ...LAYERS.filter((layer) => layer !== 'shared').map((layer) =>
              policy(layer, allowedBelow(layer)),
            ),
            policy('shared', ['shared']),
          ],
        },
      ],
    },
  },
  {
    files: ['**/*.test.ts'],
    rules: { 'max-lines-per-function': 'off', 'max-lines': 'off', 'max-nested-callbacks': 'off' },
  },
);
