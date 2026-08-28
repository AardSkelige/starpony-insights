import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"

export type ShipmentMaterials = components["schemas"]["ShipmentMaterials"]
export type ShipmentMaterialRow = components["schemas"]["ShipmentMaterialRow"]
export type ShipmentMaterialDetail = components["schemas"]["ShipmentMaterialDetail"]
export type WithoutPlanRow = components["schemas"]["WithoutPlanRow"]

/** Что человек выбрал в фильтрах. Всё это живёт в адресной строке. */
export type ShipmentMaterialsQuery = {
  dateFrom: string | null
  dateTo: string | null
  channelId: number | null
  search: string
  page: number
  ordering?: string
  pageSize?: number
}

export const shipmentMaterialsKeys = {
  list: (query: ShipmentMaterialsQuery) => ["shipments", "materials", query] as const,
  detail: (id: number, query: Omit<ShipmentMaterialsQuery, "page">) =>
    ["shipments", "materials", id, query] as const,
}

function toParams(query: ShipmentMaterialsQuery): string {
  const params = new URLSearchParams()
  if (query.dateFrom) params.set("date_from", query.dateFrom)
  if (query.dateTo) params.set("date_to", query.dateTo)
  if (query.channelId) params.set("channel_id", String(query.channelId))
  if (query.search) params.set("search", query.search)
  if (query.page > 1) params.set("page", String(query.page))
  if (query.ordering) params.set("ordering", query.ordering)
  if (query.pageSize) params.set("page_size", String(query.pageSize))
  return params.toString()
}

export function useShipmentMaterials(query: ShipmentMaterialsQuery) {
  return useQuery({
    queryKey: shipmentMaterialsKeys.list(query),
    queryFn: () => {
      const params = toParams(query)
      return api.get<ShipmentMaterials>(
        `/api/shipments/materials/${params ? `?${params}` : ""}`
      )
    },
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
export function useMaterialDetail(
  materialId: number | null,
  query: Omit<ShipmentMaterialsQuery, "page">
) {
  return useQuery({
    queryKey: shipmentMaterialsKeys.detail(materialId ?? 0, query),
    queryFn: () => {
      const params = toParams({ ...query, page: 1 })
      return api.get<ShipmentMaterialDetail>(
        `/api/shipments/materials/${materialId}/${params ? `?${params}` : ""}`
      )
    },
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
export function exportUrl(query: Omit<ShipmentMaterialsQuery, "page">): string {
  const params = toParams({ ...query, page: 1 })
  return `/api/shipments/materials/xlsx/${params ? `?${params}` : ""}`
}
