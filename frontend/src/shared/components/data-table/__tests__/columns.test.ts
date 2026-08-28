import { describe, expect, it } from "vitest"

import {
  COLUMNS as MATERIAL_COLUMNS,
  totalsFor as materialTotals,
} from "@/sections/shipments-materials/columns"
import {
  COLUMNS as PRODUCT_COLUMNS,
  totalsFor as productTotals,
} from "@/sections/shipments-products/columns"
import type { Column } from "@/shared/components/data-table"

/**
 * Описания таблиц всех разделов.
 *
 * Проверяются вместе, а не по отдельности: инварианты здесь общие, и новая
 * страница обязана попасть в этот список — иначе проверка молча перестанет
 * покрывать половину интерфейса.
 */
const TABLES = [
  {
    name: "Товары в отгрузках",
    columns: PRODUCT_COLUMNS as Column<unknown>[],
    totals: productTotals({
      quantity: "2338.000",
      free_quantity: "532.000",
      revenue_kopecks: 122265995,
      documents_count: 294,
      products_count: 66,
    }),
    /** Расчётные колонки — те, что посчитаны, а не взяты из учёта как есть. */
    computed: ["avg", "share"],
  },
  {
    name: "Материалы в отгрузках",
    columns: MATERIAL_COLUMNS as Column<unknown>[],
    totals: materialTotals({
      materials_count: 161,
      cost_kopecks: 40730717,
      cost_share: "1.00000000",
      priced_count: 134,
      unpriced_count: 27,
    }),
    computed: ["quantity", "cost", "share"],
  },
]

describe.each(TABLES)("$name", ({ columns, totals, computed }) => {
  it("итог подвала задаётся ключами существующих колонок", () => {
    // Ошибка тихая: подвал собирается по ключам, и опечатка не роняет
    // таблицу — ячейка просто остаётся пустой, и этого никто не замечает,
    // пока кто-нибудь не станет сверять сумму колонки с итогом.
    const known = new Set(columns.map((column) => column.key))
    const unknown = Object.keys(totals.values).filter((key) => !known.has(key))

    expect(unknown, `итог задан по несуществующим колонкам: ${unknown}`).toEqual([])
  })

  it("каждое расчётное число объясняет себя", () => {
    // Правило DESIGN §8. Число без формулы — незакрытая задача, а забыть
    // подсказку легче всего при добавлении колонки к готовой таблице.
    const without = columns
      .filter((column) => computed.includes(column.key) && !column.explain)
      .map((column) => column.key)

    expect(without, `нет объяснения у колонок: ${without}`).toEqual([])
  })

  it("ключи колонок не повторяются", () => {
    // Повтор ключа делает итог неоднозначным и ломает сортировку:
    // щелчок по одной колонке сортирует по другой.
    const keys = columns.map((column) => column.key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it("первая колонка — название, и она не числовая", () => {
    // По ней взгляд находит строку; выровненная вправо, она перестаёт
    // работать как якорь.
    expect(columns[0].numeric).toBeFalsy()
  })
})

/**
 * Число в подвале приходит из выборки и бывает любым, поэтому слово рядом
 * с ним обязано склоняться. Проверяется на единице: «1 наименований» —
 * самая заметная ошибка русского интерфейса, и появляется она молча,
 * стоит собрать подпись обычной подстановкой.
 */
describe("подвал склоняет существительное при числе", () => {
  it("товары — «1 наименование»", () => {
    const totals = productTotals({
      quantity: "1.000",
      free_quantity: "0.000",
      revenue_kopecks: 10000,
      documents_count: 1,
      products_count: 1,
    })

    expect(String(totals.label)).toContain("1 наименование")
  })

  it("материалы — «1 материал»", () => {
    const totals = materialTotals({
      materials_count: 1,
      cost_kopecks: 1250,
      cost_share: "1.00000000",
      priced_count: 1,
      unpriced_count: 0,
    })

    expect(String(totals.label)).toContain("1 материал")
  })
})
