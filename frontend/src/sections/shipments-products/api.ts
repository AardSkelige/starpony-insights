import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"
import {
  withQuery,
  withSelection,
  type TableQuery,
  type TableSelection,
} from "@/shared/api/table-query"

export type ShipmentProducts = components["schemas"]["ShipmentProducts"]
export type ShipmentProductRow = components["schemas"]["ShipmentProductRow"]
type ShipmentProductDetail = components["schemas"]["ShipmentProductDetail"]

const PATH = "/api/shipments/products/"

const shipmentProductsKeys = {
  list: (query: TableQuery) => ["shipments", "products", query] as const,
  detail: (id: number, query: TableSelection) =>
    ["shipments", "products", id, query] as const,
}

export function useShipmentProducts(query: TableQuery) {
  return useQuery({
    queryKey: shipmentProductsKeys.list(query),
    queryFn: () => api.get<ShipmentProducts>(withQuery(PATH, query)),
    // Смена фильтра не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые. Скелетон вместо них на секунду
    // отбирает у человека то, что он уже читал.
    placeholderData: keepPreviousData,
  })
}

/**
 * Детали строки — отдельным запросом, по раскрытию.
 *
 * Разбивка по девяти каналам и десять документов на каждую из шестидесяти
 * шести строк — шестьсот лишних строк в ответе, из которых человек
 * посмотрит одну.
 */
export function useProductDetail(productId: number | null, query: TableSelection) {
  return useQuery({
    queryKey: shipmentProductsKeys.detail(productId ?? 0, query),
    queryFn: () =>
      api.get<ShipmentProductDetail>(withSelection(`${PATH}${productId}/`, query)),
    enabled: productId !== null,
  })
}

/**
 * Ссылка на выгрузку той же выборки.
 *
 * Файл забирает браузер обычным переходом, а не fetch: так работают докачка,
 * прогресс и папка «Загрузки» — всё, что пришлось бы писать самим,
 * складывая ответ в Blob.
 *
 * Сортировка входит в ссылку: подсказка у кнопки обещает выгрузить то,
 * что на экране, «с учётом фильтров и сортировки».
 */
export function exportUrl(query: TableSelection): string {
  return withSelection(`${PATH}xlsx/`, query)
}
