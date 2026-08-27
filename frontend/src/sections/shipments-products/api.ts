import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"

export type ShipmentProducts = components["schemas"]["ShipmentProducts"]
export type ShipmentProductRow = components["schemas"]["ShipmentProductRow"]
export type ShipmentProductDetail = components["schemas"]["ShipmentProductDetail"]

/** Что человек выбрал в фильтрах. Всё это живёт в адресной строке. */
export type ShipmentProductsQuery = {
  dateFrom: string | null
  dateTo: string | null
  channelId: number | null
  search: string
  page: number
  ordering?: string
  pageSize?: number
}

export const shipmentProductsKeys = {
  list: (query: ShipmentProductsQuery) => ["shipments", "products", query] as const,
  detail: (id: number, query: Omit<ShipmentProductsQuery, "page">) =>
    ["shipments", "products", id, query] as const,
}

function toParams(query: ShipmentProductsQuery): string {
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

/**
 * Детали строки — отдельным запросом, по раскрытию.
 *
 * Разбивка по девяти каналам и десять документов на каждую из шестидесяти
 * шести строк — шестьсот лишних строк в ответе, из которых человек
 * посмотрит одну.
 */
export function useProductDetail(
  productId: number | null,
  query: Omit<ShipmentProductsQuery, "page">
) {
  return useQuery({
    queryKey: shipmentProductsKeys.detail(productId ?? 0, query),
    queryFn: () => {
      const params = toParams({ ...query, page: 1 })
      return api.get<ShipmentProductDetail>(
        `/api/shipments/products/${productId}/${params ? `?${params}` : ""}`
      )
    },
    enabled: productId !== null,
  })
}

/**
 * Ссылка на выгрузку той же выборки.
 *
 * Файл забирает браузер обычным переходом, а не fetch: так работают докачка,
 * прогресс и папка «Загрузки» — всё, что пришлось бы писать самим,
 * складывая ответ в Blob.
 */
export function exportUrl(query: Omit<ShipmentProductsQuery, "page">): string {
  // Сортировка входит в ссылку: подсказка у кнопки обещает выгрузить то,
  // что на экране, «с учётом фильтров и сортировки».
  const params = toParams({ ...query, page: 1 })
  return `/api/shipments/products/xlsx/${params ? `?${params}` : ""}`
}

export function useShipmentProducts(query: ShipmentProductsQuery) {
  return useQuery({
    queryKey: shipmentProductsKeys.list(query),
    queryFn: () => {
      const params = toParams(query)
      return api.get<ShipmentProducts>(
        `/api/shipments/products/${params ? `?${params}` : ""}`
      )
    },
    // Смена фильтра не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые. Скелетон вместо них на секунду
    // отбирает у человека то, что он уже читал.
    placeholderData: keepPreviousData,
  })
}
