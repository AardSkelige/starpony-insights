import { api, type Profile } from "@/shared/api/client"

/**
 * Кто вошёл и что ему видно.
 *
 * Список страниц приходит с сервера, из реестра `api/access.py`. Своего списка
 * на фронтенде нет намеренно: он неизбежно разъедется с тем, что защищает
 * бэкенд, и человек увидит в меню пункт, который отдаёт 403.
 */
export const sessionKeys = {
  profile: ["session", "profile"] as const,
}

export function fetchProfile() {
  return api.get<Profile>("/api/auth/me/")
}

export async function signIn(username: string, password: string) {
  // Токен CSRF нужен до отправки формы: страница входа — статика, скрытого
  // поля с токеном в ней нет, взять его неоткуда, кроме как спросить.
  await api.get<{ csrfToken: string }>("/api/auth/csrf/")
  return api.post<Profile>("/api/auth/login/", { username, password })
}

export function signOut() {
  return api.post<void>("/api/auth/logout/")
}
