import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROUTE_DIRECTORY = 'app';
const STRAY_ROUTE_DIRECTORIES: readonly string[] = ['pages', join('src', 'pages')];

describe('Next.js route directories', () => {
  it('keeps the route files in the root app directory, which makes Next ignore src/app', () => {
    expect(existsSync(join(process.cwd(), ROUTE_DIRECTORY))).toBe(true);
  });

  it.each(STRAY_ROUTE_DIRECTORIES)('has no %s directory that Next would pick up', (directory) => {
    expect(existsSync(join(process.cwd(), directory))).toBe(false);
  });
});
