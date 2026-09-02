import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"
import { withQuery, type TableQuery } from "@/shared/api/table-query"

export type Deadlines = components["schemas"]["Deadlines"]
export type DeadlineRow = components["schemas"]["DeadlineRow"]
export type DeadlineDetail = components["schemas"]["DeadlineDetail"]
export type AgeShelf = components["schemas"]["AgeShelf"]

const PATH = "/api/deadlines/"

const deadlineKeys = {
  list: (query: TableQuery) => ["deadlines", query] as const,
  detail: (agentId: number) => ["deadlines", "detail", agentId] as const,
}

export function useDeadlines(query: TableQuery) {
  return useQuery({
    queryKey: deadlineKeys.list(query),
    queryFn: () => api.get<Deadlines>(withQuery(PATH, query)),
    // Смена фильтра не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые.
    placeholderData: keepPreviousData,
  })
}

/**
 * Разбор строки едет отдельным запросом — и это решение, а не пробел.
 *
 * У «Интернет Решений» 150 неоплаченных отгрузок; приезжай они вместе
 * со строкой, они уходили бы в каждый ответ страницы, включая те случаи,
 * когда строку никто не раскрывал. У «Поставщиков» решение обратное
 * и по той же причине: там слагаемые — десяток чисел, а не полторы сотни
 * документов.
 *
 * Фильтров в ключе нет: долг — состояние на сегодня, и сузить его нечем.
 * Поиск меняет список строк, а не сами документы контрагента.
 */
export function useDeadlineDetail(agentId: number | null) {
  return useQuery({
    queryKey: deadlineKeys.detail(agentId ?? 0),
    queryFn: () => api.get<DeadlineDetail>(`${PATH}${agentId}/`),
    enabled: agentId !== null,
  })
}

/**
 * Ссылка на выгрузку.
 *
 * Файл забирает браузер обычным переходом, а не fetch: так работают докачка,
 * прогресс и папка «Загрузки» — всё, что пришлось бы писать самим,
 * складывая ответ в Blob.
 *
 * Периода в адресе нет: страница показывает весь незакрытый долг, и файл —
 * то же самое.
 */
export function exportUrl(query: { search?: string; ordering?: string }): string {
  const params = new URLSearchParams()
  if (query.search) params.set("search", query.search)
  if (query.ordering) params.set("ordering", query.ordering)
  const search = params.toString()
  return search ? `${PATH}xlsx/?${search}` : `${PATH}xlsx/`
}
