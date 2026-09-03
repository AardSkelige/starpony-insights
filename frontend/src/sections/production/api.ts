import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"

export type Products = components["schemas"]["Products"]
export type ProductRow = components["schemas"]["ProductRow"]
export type Batch = components["schemas"]["Batch"]
export type BatchLine = components["schemas"]["BatchLine"]
export type Need = components["schemas"]["Need"]
export type ProductsSummary = components["schemas"]["ProductsSummary"]
export type BatchSummary = components["schemas"]["BatchSummary"]

/**
 * Что отобрано в партию: артикул → сколько штук.
 *
 * `null` — «сколько предложит страница»: количество не закреплено и следует
 * за горизонтом. Так попадают сюда позиции, отмеченные галочкой или кнопкой
 * «Взять всё», — их числа человек не вводил, и переключатель 30/60/90 обязан
 * их менять. Число появляется, только когда его поправили руками.
 */
export type Picked = Record<string, number | null>



const PRODUCTS = "/api/production/products/"
const BATCH = "/api/production/batch/"

const keys = {
  products: (query: ProductsQuery) => ["production", "products", query] as const,
  batch: (picked: Picked, query: ProductsQuery) =>
    ["production", "batch", picked, query] as const,
}

export type ProductsQuery = {
  dateFrom: string | null
  dateTo: string | null
  search: string
  horizon: number
}

/**
 * Два запроса, а не один, — по причине изменения.
 *
 * Верхний список зависит от периода и горизонта, нижний — от того, что
 * человек отобрал. Слей их в один, и правка количества в одной строке
 * перезапрашивала бы весь каталог вместе с продажами за полгода.
 */
function productsUrl(query: ProductsQuery): string {
  const params = new URLSearchParams()
  if (query.dateFrom) params.set("date_from", query.dateFrom)
  if (query.dateTo) params.set("date_to", query.dateTo)
  if (query.search) params.set("search", query.search)
  params.set("horizon", String(query.horizon))
  return `${PRODUCTS}?${params}`
}

/**
 * Партия уходит повторяющимся `item` — по строке на позицию.
 *
 * В адресе браузера она живёт одним параметром через запятую (`use-batch.ts`):
 * ссылка так короче и читается глазами. Разворачивать её обратно — работа
 * этого модуля, и она вся здесь: два вида одной партии не должны собираться
 * в двух местах.
 */
function batchUrl(picked: Picked, query: ProductsQuery): string {
  const params = new URLSearchParams()
  for (const [article, quantity] of Object.entries(picked)) {
    // Голый артикул — «посчитай сам»: количество считает сервер из продаж
    // за период и горизонта. Разрешать его здесь нельзя: список товаров
    // приходит суженным поиском, и партия, собранная до поиска, молча
    // теряла бы всё, чего в найденном не оказалось.
    params.append("item", quantity === null ? article : `${article}:${quantity}`)
  }
  if (query.dateFrom) params.set("date_from", query.dateFrom)
  if (query.dateTo) params.set("date_to", query.dateTo)
  params.set("horizon", String(query.horizon))
  return `${BATCH}?${params}`
}

export function useProducts(query: ProductsQuery) {
  return useQuery({
    queryKey: keys.products(query),
    queryFn: () => api.get<Products>(productsUrl(query)),
    // Смена горизонта не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые.
    placeholderData: keepPreviousData,
  })
}

export function useBatch(picked: Picked, query: ProductsQuery) {
  return useQuery({
    // Поиск в ключ не входит: он сужает список слева, но партию не трогает.
    queryKey: keys.batch(picked, { ...query, search: "" }),
    queryFn: () => api.get<Batch>(batchUrl(picked, query)),
    // Ради этого страница и существует: прибавил десять флаконов — увидел,
    // что докупать. Опустей правая колонка на каждое нажатие, связь между
    // причиной и следствием пришлось бы держать в голове.
    placeholderData: keepPreviousData,
  })
}
