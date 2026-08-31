import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"
import {
  withQuery,
  withSelection,
  type TableQuery,
  type TableSelection,
} from "@/shared/api/table-query"

export type Channels = components["schemas"]["Channels"]
export type ChannelRow = components["schemas"]["ChannelRow"]
export type Receipt = components["schemas"]["Receipt"]
export type Dynamics = components["schemas"]["Dynamics"]
export type ChannelTop = components["schemas"]["ChannelTop"]

const PATH = "/api/channels/"

const channelsKeys = {
  list: (query: TableQuery) => ["channels", query] as const,
}

export function useChannels(query: TableQuery) {
  return useQuery({
    queryKey: channelsKeys.list(query),
    queryFn: () => api.get<Channels>(withQuery(PATH, query)),
    // Смена фильтра не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые.
    placeholderData: keepPreviousData,
  })
}

/**
 * Отдельного запроса за разбором строки нет — как у «Поставщиков».
 *
 * Каналов девять, и всё, чем строка себя объясняет — разброс чека, пятёрка
 * покупателей, пятёрка товаров и свой ряд по времени, — приходит вместе
 * с ней. Это десяток чисел и два коротких списка, а не история на восемьсот
 * строк, ради которой на страницах материалов заведён отдельный запрос.
 */

/**
 * Ссылка на выгрузку той же выборки.
 *
 * Файл забирает браузер обычным переходом, а не fetch: так работают докачка,
 * прогресс и папка «Загрузки».
 */
export function exportUrl(query: TableSelection): string {
  return withSelection(`${PATH}xlsx/`, query)
}

/**
 * Цвет канала в графиках — по номеру слота, закреплённому сервером.
 *
 * Слот приходит с ответом, а не вычисляется здесь: он считается по выручке
 * за всю историю, чтобы смена периода не перекрашивала каналы. Девятый
 * канал слота не имеет — он рисуется приглушённым, как «Другое»: повторить
 * цвет значило бы сказать «это тот же канал».
 */
export function slotColor(slot: number | null): string {
  return slot ? `var(--chart-${slot})` : "var(--muted-foreground)"
}
