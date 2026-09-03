import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"
import { withQuery, type TableQuery } from "@/shared/api/table-query"

export type Profitability = components["schemas"]["Profitability"]
export type ProfitabilityRow = components["schemas"]["ProfitabilityRow"]
export type ProfitabilityFamily = components["schemas"]["ProfitabilityFamily"]

/**
 * По какому событию считается выручка.
 *
 * `sold` — деньги за товар: так считает МойСклад, и товар по договору
 * комиссии становится проданным с приходом отчёта комиссионера.
 * `shipped` — всё, что уехало со склада. На 02.09 разница 281 126 ₽,
 * и обе цифры верны — это разные вопросы, а не расхождение.
 */
export type Basis = "sold" | "shipped"

/** Своё у этой страницы: база расчёта и подарки. */
export type ProfitabilityView = {
  basis: Basis
  withFree: boolean
}

const PATH = "/api/profitability/"

const profitabilityKeys = {
  list: (query: TableQuery, view: ProfitabilityView) =>
    ["profitability", query, view] as const,
}

/**
 * Адрес запроса: общая выборка плюс своё у раздела.
 *
 * Базы и подарков нет в `TableQuery` намеренно — у остальных девяти страниц
 * такого выбора не существует, и общий тип обзавёлся бы полями, которые
 * никто не заполняет. Умолчания в адрес не пишутся: ссылка должна говорить
 * только о том, что человек выбрал.
 */
function url(query: TableQuery, view: ProfitabilityView): string {
  const base = withQuery(PATH, query)
  const extra = new URLSearchParams()
  if (view.basis !== "sold") extra.set("basis", view.basis)
  if (view.withFree) extra.set("with_free", "true")
  const tail = extra.toString()
  if (!tail) return base
  return base.includes("?") ? `${base}&${tail}` : `${base}?${tail}`
}

export function useProfitability(query: TableQuery, view: ProfitabilityView) {
  return useQuery({
    queryKey: profitabilityKeys.list(query, view),
    queryFn: () => api.get<Profitability>(url(query, view)),
    // Смена базы не должна опустошать экран: старые строки остаются
    // и приглушаются, пока едут новые.
    placeholderData: keepPreviousData,
  })
}

/**
 * Ссылка на выгрузку.
 *
 * Файл забирает браузер обычным переходом, а не fetch: так работают докачка,
 * прогресс и папка «Загрузки». База расчёта уходит в адрес — она попадает
 * и в имя файла, и в имя листа: два файла за один период иначе выглядят
 * одинаково и расходятся на 281 126 ₽.
 */
export function exportUrl(
  query: Omit<TableQuery, "page">,
  view: ProfitabilityView
): string {
  return url({ ...query, page: 1 }, view).replace(PATH, `${PATH}xlsx/`)
}
