import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { PUBLIC_DIRECTORY, PUBLIC_FILE } from './public-files';
import type { PublicFile } from './public-files';
import { STORAGE_KEY } from './storage-keys';
import type { StorageKey } from './storage-keys';

const KEY_READERS: ReadonlyArray<readonly [StorageKey, PublicFile]> = [
  [STORAGE_KEY.LANGUAGE, PUBLIC_FILE.HOME],
  [STORAGE_KEY.LANGUAGE, PUBLIC_FILE.ATLAS],
  [STORAGE_KEY.THEME, PUBLIC_FILE.HOME],
  [STORAGE_KEY.THEME, PUBLIC_FILE.WORKBOOK],
  [STORAGE_KEY.THEME, PUBLIC_FILE.KIRA],
  [STORAGE_KEY.WORKBOOK, PUBLIC_FILE.WORKBOOK],
];

describe('legacy localStorage keys', () => {
  it.each(KEY_READERS)('keeps %s as a plain string literal in %s', async (key, file) => {
    const page = await readFile(join(process.cwd(), PUBLIC_DIRECTORY, file), 'utf8');

    expect(page).toContain(`'${key}'`);
  });
});
