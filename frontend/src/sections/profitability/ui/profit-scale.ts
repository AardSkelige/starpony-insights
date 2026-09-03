import * as React from "react"

/**
 * Масштаб полосы прибыли: наибольшая прибыль на показанной странице.
 *
 * Через контекст, а не параметром колонки: колонка описывается данными,
 * и `COLUMNS` — модульная константа, которую разбирает общая проверка
 * таблиц. Фабрика колонок ради одного числа сломала бы и то, и другое.
 *
 * **Меряется от страницы, а не от итога.** Строки сравниваются между собой:
 * шкала от всей прибыли сплющила бы их у кромки — у лидера всего 17,5 %.
 * По модулю, чтобы убыточная строка тоже имела длину.
 *
 * Файл без разметки намеренно: рядом с компонентом хук ломает горячую
 * перезагрузку — правило `react-refresh/only-export-components`.
 */
export const ProfitScaleContext = React.createContext(0)

/** Наибольшая прибыль по модулю среди показанных строк. */
export function maxProfit(rows: { profit_kopecks: number | null }[]): number {
  return rows.reduce(
    (top, row) => Math.max(top, Math.abs(row.profit_kopecks ?? 0)),
    0
  )
}

/** Доля полосы от наибольшей на странице, в процентах. */
export function useProfitWidth(profit: number | null): string {
  const max = React.useContext(ProfitScaleContext)
  if (profit === null || max <= 0) return "0%"
  return `${(Math.abs(profit) / max) * 100}%`
}
