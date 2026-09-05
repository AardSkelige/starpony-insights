import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"
import {
  withQuery,
  withSelection,
  type TableQuery,
  type TableSelection,
} from "@/shared/api/table-query"

export type Inventory = components["schemas"]["Inventory"]
export type InventoryRow = components["schemas"]["InventoryRow"]
export type InventoryCoverage = components["schemas"]["Coverage"]
export type InventoryWorst = components["schemas"]["Worst"]
export type InventoryRepeats = components["schemas"]["Repeats"]
export type InventoryDocuments = components["schemas"]["InventoryDocuments"]

/** Разрезы этой страницы: склад и папка номенклатуры. */
export type InventoryCuts = { store: string; folder: string }

const PATH = "/api/inventory/"

const inventoryKeys = {
  list: (query: TableQuery, cuts: InventoryCuts) =>
    ["inventory", query, cuts] as const,
}

/**
 * Склад и папка уходят строкой, а не идентификатором.
 *
 * Склада как сущности у нас нет — он приходит именем внутри инвентаризации,
 * и синтетический номер в ссылке означал бы разное в разные дни: заведи
 * человек четвёртый склад, `store=2` открыл бы чужой. Имя переживает это.
 */
function withCuts(path: string, cuts: InventoryCuts): string {
  const url = new URL(path, window.location.origin)
  if (cuts.store) url.searchParams.set("store", cuts.store)
  if (cuts.folder) url.searchParams.set("folder", cuts.folder)
  return `${url.pathname}${url.search}`
}

export function useInventory(query: TableQuery, cuts: InventoryCuts) {
  return useQuery({
    queryKey: inventoryKeys.list(query, cuts),
    queryFn: () => api.get<Inventory>(withCuts(withQuery(PATH, query), cuts)),
    // Смена разреза не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые.
    placeholderData: keepPreviousData,
  })
}

/**
 * Отдельного запроса за разбором строки нет — как у «Поставщиков».
 *
 * Всё, чем строка себя объясняет, приходит вместе с ней: последний пересчёт,
 * себестоимость, которой посчитаны деньги, число пересчётов и расхождений,
 * остаток на сегодня. Это десяток чисел, а не список, и второй запрос
 * добавил бы задержку там, где ответ уже на руках.
 */

/** Ссылка на выгрузку той же выборки — файл забирает браузер переходом. */
export function exportUrl(query: TableSelection, cuts: InventoryCuts): string {
  return withCuts(withSelection(`${PATH}xlsx/`, query), cuts)
}
