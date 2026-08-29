import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"
import {
  withQuery,
  withSelection,
  type TableQuery,
  type TableSelection,
} from "@/shared/api/table-query"

export type SupplyMaterials = components["schemas"]["SupplyMaterials"]
export type SupplyMaterialRow = components["schemas"]["SupplyMaterialRow"]
export type SupplyMaterialDetail = components["schemas"]["SupplyMaterialDetail"]
export type PricePoint = components["schemas"]["PricePoint"]
export type Purchase = components["schemas"]["Purchase"]
export type SupplierPrice = components["schemas"]["SupplierPrice"]

const PATH = "/api/supplies/materials/"

const supplyMaterialsKeys = {
  list: (query: TableQuery) => ["supplies", "materials", query] as const,
  detail: (id: number, query: TableSelection) =>
    ["supplies", "materials", id, query] as const,
}

export function useSupplyMaterials(query: TableQuery) {
  return useQuery({
    queryKey: supplyMaterialsKeys.list(query),
    queryFn: () => api.get<SupplyMaterials>(withQuery(PATH, query)),
    // Смена фильтра не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые.
    placeholderData: keepPreviousData,
  })
}

/**
 * Разбор одного материала — отдельным запросом, по раскрытию.
 *
 * Ряд цен для линии приходит вместе со строкой: он короткий, в среднем
 * две точки на материал. А история с номерами приёмок, поставщиками
 * и суммами — только по запросу: на двести двенадцать строк это восемьсот
 * строк, из которых человек посмотрит одну.
 */
export function useSupplyMaterialDetail(
  materialId: number | null,
  query: TableSelection
) {
  return useQuery({
    queryKey: supplyMaterialsKeys.detail(materialId ?? 0, query),
    queryFn: () =>
      api.get<SupplyMaterialDetail>(withSelection(`${PATH}${materialId}/`, query)),
    enabled: materialId !== null,
  })
}

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
