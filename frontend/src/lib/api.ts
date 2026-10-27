import type { ApiProblem, Issue } from './types';

export class ApiError extends Error {
  code: string;
  issues: Issue[];
  status: number;
  constructor(problem: ApiProblem, status: number) {
    super(problem.message);
    this.name = 'ApiError';
    this.code = problem.code;
    this.issues = problem.issues ?? [];
    this.status = status;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: {
        'X-Komplekt-Request': '1',
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(
      {
        code: 'connection',
        message:
          'Не удалось связаться с приложением. Проверьте, что оно запущено, и повторите действие.',
        issues: [],
      },
      0,
    );
  }
  if (!response.ok) {
    let problem: ApiProblem;
    try {
      problem = (await response.json()) as ApiProblem;
    } catch {
      problem = {
        code: 'server',
        message:
          'Не получилось выполнить действие. Обновите страницу и проверьте данные перед повторной попыткой.',
        issues: [],
      };
    }
    throw new ApiError(
      {
        ...problem,
        message: problem.message || 'Не получилось выполнить действие. Попробуйте ещё раз.',
      },
      response.status,
    );
  }
  return (await response.json()) as T;
}

export function problemFrom(error: unknown): ApiProblem {
  if (error instanceof ApiError) return error;
  return {
    code: 'unexpected',
    message: 'Не получилось выполнить действие. Повторите попытку.',
    issues: [],
  };
}

export async function downloadPdf(id: string, filename: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`/api/quotes/${encodeURIComponent(id)}/pdf`);
  } catch {
    throw new ApiError(
      {
        code: 'connection',
        message: 'Не удалось скачать PDF. Проверьте, что приложение запущено, и попробуйте снова.',
        issues: [],
      },
      0,
    );
  }
  if (!response.ok) {
    let problem: ApiProblem;
    try {
      problem = (await response.json()) as ApiProblem;
    } catch {
      problem = {
        code: 'download',
        message: 'Не удалось скачать PDF. Документ останется в истории — попробуйте ещё раз.',
        issues: [],
      };
    }
    throw new ApiError(problem, response.status);
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
