const STORAGE_KEY = 'komplekt-quote-key';

interface StoredKey {
  key: string;
  revision: number;
  requestId: string;
}

/** Вернуть ключ одного нажатия «Сохранить КП», пока ревизия и заявка те же. */
export function quoteKey(revision: number, requestId: string): string {
  const saved = readKey();
  if (saved?.revision === revision && saved.requestId === requestId) return saved.key;
  const key = crypto.randomUUID().replaceAll('-', '');
  const value: StoredKey = { key, revision, requestId };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  return key;
}

/** Забыть ключ после успешного выпуска. */
export function clearQuoteKey(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

function readKey(): StoredKey | null {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<StoredKey>;
    if (
      typeof value.key === 'string' &&
      /^[a-f0-9]{32}$/.test(value.key) &&
      typeof value.revision === 'number' &&
      typeof value.requestId === 'string'
    ) {
      return { key: value.key, revision: value.revision, requestId: value.requestId };
    }
  } catch {
    return null;
  }
  return null;
}
