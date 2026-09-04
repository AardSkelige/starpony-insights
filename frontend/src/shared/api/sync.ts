import {
  useIsMutating,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import * as React from "react"

import { api, ApiError } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"

type SyncRun = components["schemas"]["SyncRun"]
type SyncStatus = components["schemas"]["SyncStatus"]

/** Как часто спрашивать, не закончился ли прогон. */
const POLL_MS = 3000

/** Как часто меняется фраза ожидания. */
const PHRASE_MS = 4000

/**
 * Ключ мутации «Обновить».
 *
 * Нужен не ради удобства: пока идёт **свой** прогон, опрос статуса обязан
 * работать, а узнать о нём иначе неоткуда — `useSyncStatus` и `useRefresh`
 * живут в разных местах страницы.
 */
const REFRESH_KEY = ["sync", "refresh"] as const

/**
 * Чем занять человека, пока крутится стрелка.
 *
 * Меняются по кругу, раз в несколько секунд, — и это часть ответа
 * на вопрос «зависло или нет»: неподвижная надпись выглядит одинаково
 * у живого прогона и у мёртвого. Правду при этом несёт счётчик рядом,
 * а не фраза: она только показывает, что жизнь есть.
 *
 * **Ни одна не склоняет «МойСклад»** — это название, а не слово.
 */
const WAITING_PHRASES = [
  "тормошим МойСклад",
  "считаем баночки",
  "пересчитываем гривы и хвосты",
  "сверяем с учётом",
  "раскладываем по полочкам",
  "уговариваем МойСклад отдать данные",
  "проверяем, всё ли доехало",
]

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

  // Идёт ли **наш** запрос «Обновить». Без этого опрос не включался вовсе:
  // статус приходил один раз при загрузке страницы со словом «не идёт»,
  // интервал оставался выключенным, и всё время прогона счётчик показывал
  // ноль из нуля. Чужой прогон при этом опрашивался нормально — оттого
  // ошибка и не бросалась в глаза.
  const refreshing = useIsMutating({ mutationKey: REFRESH_KEY }) > 0

  const query = useQuery({
    queryKey: ["sync", "status"],
    queryFn: () => api.get<SyncStatus>("/api/sync/status/"),
    refetchInterval: (query) =>
      query.state.data?.running || refreshing ? POLL_MS : false,
  })

  const running = query.data?.running ?? false

  React.useEffect(() => {
    if (wasRunning.current && !running) {
      queryClient.invalidateQueries()
    }
    wasRunning.current = running
  }, [running, queryClient])

  return {
    running,
    startedAt: query.data?.started_at ?? null,
    // Настоящий прогресс: сколько сущностей уже закрыто и что идёт сейчас.
    done: query.data?.done ?? 0,
    total: query.data?.total ?? 0,
    stage: query.data?.stage ?? "",
    // Фраза крутится своим ходом, а не считается из времени начала.
    // Считанная — менялась бы только вместе с ответом сервера, то есть
    // рывками раз в три секунды и вовсе никогда, пока опрос выключен.
    phrase: useWaitingPhrase(running || refreshing),
  }
}

/**
 * Фраза ожидания, меняющаяся сама по себе.
 *
 * **Это не украшение, а половина ответа на «зависло или нет».** Вторая
 * половина — счётчик сущностей, но он появляется только когда сервер
 * закроет первую из тринадцати, а до тех пор на экране обязано двигаться
 * хоть что-то.
 */
function useWaitingPhrase(active: boolean): string {
  const [tick, setTick] = React.useState(0)

  React.useEffect(() => {
    if (!active) return
    const timer = setInterval(() => setTick((value) => value + 1), PHRASE_MS)
    return () => clearInterval(timer)
  }, [active])

  // Счётчик не сбрасывается между прогонами намеренно: сброс — это
  // присваивание состояния прямо в эффекте, которое запрещено правилом
  // React Compiler, а пользы от него нет. Следующее ожидание просто
  // начнётся с другой фразы, и это скорее приятно.

  return WAITING_PHRASES[tick % WAITING_PHRASES.length]
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
    // Ключ объявлен, чтобы `useSyncStatus` увидел идущий прогон и включил
    // опрос: иначе прогресс молчит всё время, пока человек ждёт.
    mutationKey: REFRESH_KEY,
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
  running: boolean,
  progress?: { done: number; total: number; stage: string; phrase: string }
): string | null {
  // `running` покрывает и чужой прогон, и свой после перезагрузки страницы,
  // когда состояние мутации уже потеряно.
  if (refresh.isPending || running) {
    const phrase = progress?.phrase ?? WAITING_PHRASES[0]
    // Счётчик — то, что отличает идущий прогон от зависшего. Пока сервер
    // не закрыл первую сущность, показывать нечего, и остаётся фраза:
    // «0 из 13» выглядело бы поломкой, а не началом.
    if (progress && progress.total > 0 && progress.done > 0) {
      return `${phrase}… ${progress.done} из ${progress.total}${progress.stage ? ` · ${progress.stage}` : ""}`
    }
    return `${phrase}…`
  }

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
