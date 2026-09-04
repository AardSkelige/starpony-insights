import { useQuery } from "@tanstack/react-query"

import { api } from "@/shared/api/client"
import type { components } from "@/shared/api/schema"

export type Home = components["schemas"]["Home"]
export type HomeSignal = components["schemas"]["HomeSignal"]
export type HomeMisplaced = components["schemas"]["HomeMisplaced"]
export type HomeFigure = components["schemas"]["HomeFigure"]
export type HomeMonth = components["schemas"]["HomeMonth"]
export type HomeMargin = components["schemas"]["HomeMargin"]
export type HomeChange = components["schemas"]["HomeChange"]
export type HomeChannel = components["schemas"]["HomeChannel"]
export type HomeListRow = components["schemas"]["HomeListRow"]

const PATH = "/api/home/"

const homeKeys = {
  page: ["home"] as const,
}

/**
 * Главная одним запросом.
 *
 * Плитки не тянутся по отдельности намеренно: они считаются по одним и тем же
 * данным — каталогу, остаткам, отгрузкам за месяц, — и шесть запросов
 * повторили бы этот обход шесть раз. Плюс состав ответа зависит от доступов,
 * а решается это на сервере в одном месте.
 *
 * `TableQuery` здесь нет вовсе: у страницы нет ни фильтров, ни страниц,
 * ни сортировки. Окно выбирает сервер — последний полный месяц, — и выбирать
 * его руками нечего.
 */
export function useHome() {
  return useQuery({
    queryKey: homeKeys.page,
    queryFn: () => api.get<Home>(PATH),
  })
}
