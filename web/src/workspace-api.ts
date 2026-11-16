export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function request<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  let csrf = "";
  if (method !== "GET") {
    const response = await fetch("/api/v1/auth/csrf", {
      credentials: "same-origin",
    });
    const body = await response.json();
    if (!response.ok) throw new ApiError(response.status, body.title);
    csrf = body.csrf_token;
  }
  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
    signal: AbortSignal.timeout(15000),
  });
  const body = await response.json();
  if (!response.ok) throw new ApiError(response.status, body.title);
  return body as T;
}
