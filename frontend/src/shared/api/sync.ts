import { useMutation, useQueryClient } from "@tanstack/react-query"

import { api, ApiError } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"

export type SyncRun = components["schemas"]["SyncRun"]

/**
 * Кнопка «Обновить»: единственное место, где запрос человека доходит
 * до МойСклада.
 *
 * Проход занимает около двадцати секунд — столько же, сколько ночной,
 * потому что он и есть ночной. Поэтому кнопка блокируется на всё время,
 * а не показывает мгновенный отклик, которого не было.
 */
export function useRefresh() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post<SyncRun>("/api/sync/refresh/"),
    onSuccess: () => {
      // Обновились все разделы сразу, а не только открытый: перечитываем
      // всё, что успело закешироваться.
      queryClient.invalidateQueries()
    },
  })
}

/** Текст отказа — он приходит с сервера и уже написан для человека. */
export function refusalText(error: unknown): string | null {
  if (error instanceof ApiError && [409, 429].includes(error.status)) {
    return error.message
  }
  return null
}
