// Служебный запуск для управляемого предпросмотра. Обычный запуск — start.cmd.
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
import { existsSync } from 'node:fs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const portIndex = args.indexOf('--port');
const port = portIndex >= 0 ? args[portIndex + 1] : (process.env.PORT || '5173');
if (!/^\d{1,5}$/.test(port) || Number(port) < 1 || Number(port) > 65535) {
  throw new Error('Некорректный порт предпросмотра');
}
// В изолированном предпросмотре абсолютная ссылка venv на /tmp недоступна.
// Необязательный локальный интерпретатор в tmp устраняет только эту настройку.
const portable = resolve(root, 'tmp/preview-python/bin/python3.13');
const python = existsSync(portable) ? portable : resolve(root, '.venv/bin/python');
const environment = { ...process.env,
  PYTHONPATH: resolve(root, '.venv/lib/python3.13/site-packages'),
};
const child = spawn(python, [
  '-m', 'uvicorn', 'app.main:create_app', '--factory', '--host', '0.0.0.0', '--port', port,
], { cwd: root, stdio: 'inherit', env: environment });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
child.on('exit', code => process.exit(code ?? 1));
