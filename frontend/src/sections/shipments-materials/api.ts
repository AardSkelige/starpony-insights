import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"
import {
  withQuery,
  withSelection,
  type TableQuery,
  type TableSelection,
} from "@/shared/api/table-query"

export type ShipmentMaterials = components["schemas"]["ShipmentMaterials"]
export type ShipmentMaterialRow = components["schemas"]["ShipmentMaterialRow"]
export type ShipmentMaterialDetail = components["schemas"]["ShipmentMaterialDetail"]
export type WithoutPlanRow = components["schemas"]["WithoutPlanRow"]
export type MaterialCoverage = components["schemas"]["MaterialCoverage"]
export type MaterialRate = components["schemas"]["MaterialRate"]
export type MaterialDistribution = components["schemas"]["MaterialDistribution"]

const PATH = "/api/shipments/materials/"

const shipmentMaterialsKeys = {
  list: (query: TableQuery) => ["shipments", "materials", query] as const,
  detail: (id: number, query: TableSelection) =>
    ["shipments", "materials", id, query] as const,
}

export function useShipmentMaterials(query: TableQuery) {
  return useQuery({
    queryKey: shipmentMaterialsKeys.list(query),
    queryFn: () => api.get<ShipmentMaterials>(withQuery(PATH, query)),
    // Смена фильтра не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые.
    placeholderData: keepPreviousData,
  })
}

/**
 * Разбор одного материала — отдельным запросом, по раскрытию.
 *
 * У воды пятьдесят девять изделий-источников, и на сто шестьдесят одну строку
 * это девять тысяч лишних строк в ответе, из которых человек посмотрит одну.
 */
export function useMaterialDetail(materialId: number | null, query: TableSelection) {
  return useQuery({
    queryKey: shipmentMaterialsKeys.detail(materialId ?? 0, query),
    queryFn: () =>
      api.get<ShipmentMaterialDetail>(withSelection(`${PATH}${materialId}/`, query)),
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
