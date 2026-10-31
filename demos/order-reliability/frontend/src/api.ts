export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function request<T>(path: string, method: 'GET' | 'POST' = 'GET'): Promise<T> {
  const response = await fetch(`/api${path}`, { method });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      body?.error?.code ?? 'request_failed',
      body?.error?.message ?? `HTTP ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}
