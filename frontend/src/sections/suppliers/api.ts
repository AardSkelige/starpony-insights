import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"
import {
  withQuery,
  withSelection,
  type TableQuery,
  type TableSelection,
} from "@/shared/api/table-query"

export type Suppliers = components["schemas"]["Suppliers"]
export type SupplierRow = components["schemas"]["SupplierRow"]
export type Regularity = components["schemas"]["Regularity"]
export type LeadTime = components["schemas"]["LeadTime"]

const PATH = "/api/suppliers/"

const suppliersKeys = {
  list: (query: TableQuery) => ["suppliers", query] as const,
}

export function useSuppliers(query: TableQuery) {
  return useQuery({
    queryKey: suppliersKeys.list(query),
    queryFn: () => api.get<Suppliers>(withQuery(PATH, query)),
    // Смена фильтра не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые.
    placeholderData: keepPreviousData,
  })
}

/**
 * Отдельного запроса за разбором строки здесь нет — и это решение, а не пробел.
 *
 * На соседних страницах разбор едет по раскрытию: история закупок материала
 * это восемьсот строк на двести двенадцать наименований, и тянуть их сразу
 * было бы расточительно. Здесь поставщиков двадцать три, и всё, чем строка
 * себя объясняет — разбросы, знаменатели медиан, число позиций и пришедших
 * даром, — уже пришло вместе с ней: это десяток чисел, а не список.
 *
 * Запрос по раскрытию добавил бы задержку там, где ответ уже на руках.
 */

/**
 * Ссылка на выгрузку той же выборки.
 *
 * Файл забирает браузер обычным переходом, а не fetch: так работают докачка,
 * прогресс и папка «Загрузки» — всё, что пришлось бы писать самим,
 * складывая ответ в Blob.
 */
export function exportUrl(query: TableSelection): string {
  return withSelection(`${PATH}xlsx/`, query)
}
