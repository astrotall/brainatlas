export const STORAGE_KEY = {
  LANGUAGE: 'conn_lang',
  THEME: 'neuroctivity-theme',
  WORKBOOK: 'neuroctivity-workbook-v1',
} as const;

export type StorageKey = (typeof STORAGE_KEY)[keyof typeof STORAGE_KEY];
