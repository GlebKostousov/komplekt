import type { State } from './types';

/** Единое состояние экранов. Страницы читают его и возвращают ответ сервера через applyState. */
export const workspace = $state<{ state: State | null }>({ state: null });

/** Заменить состояние ответом сервера. */
export function applyState(next: State): void {
  workspace.state = next;
}
