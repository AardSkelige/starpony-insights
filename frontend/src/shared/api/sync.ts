import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import * as React from "react"

import { api, ApiError } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"

type SyncRun = components["schemas"]["SyncRun"]
type SyncStatus = components["schemas"]["SyncStatus"]

/** Как часто спрашивать, не закончился ли прогон. */
const POLL_MS = 3000

/**
 * Идёт ли синхронизация — по данным сервера, а не по памяти вкладки.
 *
 * Без этого состояние «идёт» теряется при перезагрузке страницы у того, кто
 * нажал кнопку, а остальные четверо не видят его вовсе и жмут впустую.
 *
 * Пока прогон идёт, статус опрашивается; как только закончился — данные
 * разделов перечитываются, потому что они только что изменились.
 */
export function useSyncStatus() {
  const queryClient = useQueryClient()
  const wasRunning = React.useRef(false)

  const query = useQuery({
    queryKey: ["sync", "status"],
    queryFn: () => api.get<SyncStatus>("/api/sync/status/"),
    refetchInterval: (query) => (query.state.data?.running ? POLL_MS : false),
  })

  const running = query.data?.running ?? false

  React.useEffect(() => {
    if (wasRunning.current && !running) {
      queryClient.invalidateQueries()
    }
    wasRunning.current = running
  }, [running, queryClient])

  return { running, startedAt: query.data?.started_at ?? null }
}

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
    onSettled: () => {
      // И статус тоже: прогон закончился, кнопка должна разблокироваться
      // у всех, кто сейчас смотрит на страницу.
      queryClient.invalidateQueries({ queryKey: ["sync", "status"] })
    },
  })
}

/** Текст отказа — он приходит с сервера и уже написан для человека. */
function refusalText(error: unknown): string | null {
  if (error instanceof ApiError && [409, 429].includes(error.status)) {
    return error.message
  }
  return null
}

/**
 * Что сказать про последнее нажатие «Обновить».
 *
 * Показывать это обязательно: прогон почти всегда заканчивается теми же
 * числами на экране, и без явного ответа кнопка выглядит сломанной.
 *
 * Живёт рядом с самой кнопкой, а не на странице: текст один и тот же
 * на всех десяти разделах, а разойдись он — человек по формулировке решал бы,
 * что разделы обновляются по-разному.
 */
export function refreshNote(
  refresh: ReturnType<typeof useRefresh>,
  running: boolean
): string | null {
  // `running` покрывает и чужой прогон, и свой после перезагрузки страницы,
  // когда состояние мутации уже потеряно.
  if (refresh.isPending || running) return "идёт обновление из МойСклада…"

  const refusal = refusalText(refresh.error)
  if (refusal) return refusal

  if (refresh.isError) return "обновить не удалось"

  if (refresh.isSuccess) {
    const run = refresh.data
    // Прогон отвечает двухсотым и когда часть сущностей не доехала:
    // предохранитель мог остановить его после двух справочников из семи.
    // Сказать «обновлено» в этом случае — соврать ровно там, где человек
    // решает, доверять ли числам на экране.
    if (run.status !== "success") {
      return `${run.status_label.toLowerCase()} — часть данных могла не обновиться`
    }
    const seconds = run.duration_seconds
    return seconds ? `обновлено за ${seconds.toFixed(0)} с` : "обновлено"
  }

  return null
}
