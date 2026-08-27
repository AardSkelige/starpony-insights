import type { components } from "@/shared/api/schema"

export type Profile = components["schemas"]["Profile"]
export type Page = components["schemas"]["Page"]

/** Сервер ответил, но отказал. Код нужен, чтобы отличить «не вошёл» от «нет прав». */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

function csrfToken(): string {
  // Django кладёт токен в куку; заголовок из неё же. Читать document.cookie
  // приходится потому, что сама кука не HttpOnly — так и задумано,
  // иначе фронтенд не смог бы подтвердить запрос.
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : ""
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method ?? "GET"
  const needsCsrf = !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)

  const response = await fetch(path, {
    ...init,
    // Куки сессии отправляются всегда: адрес у фронтенда и API один и тот же,
    // и в разработке (через прокси), и в проде (за общим Caddy).
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(needsCsrf ? { "X-CSRFToken": csrfToken() } : {}),
      ...init.headers,
    },
  })

  if (response.status === 204) {
    return undefined as T
  }

  const body = await response.json().catch(() => null)

  if (!response.ok) {
    throw new ApiError(response.status, body?.detail ?? "Не удалось выполнить запрос")
  }

  return body as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: data ? JSON.stringify(data) : undefined }),
}
