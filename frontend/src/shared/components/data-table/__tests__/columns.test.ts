import { describe, expect, it } from "vitest"

import {
  COLUMNS as CHANNEL_COLUMNS,
  totalsFor as channelTotals,
} from "@/sections/channels/columns"
import {
  COLUMNS as DEADLINE_COLUMNS,
  totalsFor as deadlineTotals,
} from "@/sections/deadlines/columns"
import {
  COLUMNS as MATERIAL_COLUMNS,
  totalsFor as materialTotals,
} from "@/sections/shipments-materials/columns"
import {
  COLUMNS as PRODUCT_COLUMNS,
  totalsFor as productTotals,
} from "@/sections/shipments-products/columns"
import {
  COLUMNS as SUPPLIER_COLUMNS,
  totalsFor as supplierTotals,
} from "@/sections/suppliers/columns"
import {
  COLUMNS as SUPPLY_COLUMNS,
  totalsFor as supplyTotals,
} from "@/sections/supplies-materials/columns"
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
      revenue_share: "1.00000000",
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
  {
    name: "Материалы в приёмках",
    columns: SUPPLY_COLUMNS as Column<unknown>[],
    totals: supplyTotals({
      materials_count: 212,
      amount_kopecks: 87971611,
      amount_share: "1.00000000",
      priced_count: 188,
      unpriced_count: 24,
      documents_count: 93,
      suppliers_count: 22,
    }),
    // «Закуплено» здесь взято из учёта как есть, а не посчитано, — но
    // подстрочник «в т.ч. даром» требует объяснения не меньше: без него
    // разница между количеством и оплаченным количеством не читается.
    computed: ["quantity", "amount", "price", "change", "supplies"],
  },
  {
    name: "Поставщики",
    columns: SUPPLIER_COLUMNS as Column<unknown>[],
    totals: supplierTotals({
      suppliers_count: 23,
      supplies_count: 95,
      amount_kopecks: 90407611,
      amount_share: "1.00000000",
      materials_count: 212,
    }),
    // «Поставок» здесь взято из учёта как есть, но подстрочник «дней
    // поставок» требует объяснения не меньше: без него непонятно, почему
    // приёмок четырнадцать, а промежутков считается одиннадцать.
    computed: ["supplies", "share", "materials", "regularity", "lead_time"],
  },
  {
    name: "Каналы продаж",
    columns: CHANNEL_COLUMNS as Column<unknown>[],
    totals: channelTotals({
      channels_count: 9,
      shipments_count: 305,
      revenue_kopecks: 125337245,
      revenue_share: "1.00000000",
      buyers_count: 70,
      products_count: 66,
    }),
    // «Отгрузок» и «Покупателей» взяты из учёта как есть, но объяснения
    // требуют не меньше расчётных: первое несёт подстрочник «даром»,
    // второе — единицу, которая не человек, а площадка.
    computed: ["revenue", "share", "shipments", "receipt", "buyers", "products"],
  },
  {
    name: "Сроки оплаты",
    columns: DEADLINE_COLUMNS as Column<unknown>[],
    totals: deadlineTotals({
      counterparties_count: 2,
      documents_count: 24,
      debt_kopecks: 17636015,
      debt_share: "1.00000000",
      oldest_age_days: 93,
    }),
    // «Просрочено» — расчётное вдвойне: считается из отсрочки, которой
    // ни у кого нет, и прочерк там означает «посчитать не из чего»,
    // а не «срок соблюдён». Без подсказки это не прочитать.
    // «Долг» взят из учёта вычитанием, но объяснения требует не меньше
    // расчётных: из него исключены отгрузки по комиссии, и без формулы
    // разница с суммой отгруженного выглядит потерянными деньгами.
    // «Старейший долг» — вообще не срок, и сказать это может только подсказка.
    computed: ["debt", "share", "overdue", "oldest"],
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
 *
 * Сверяется **конец строки**, а не вхождение. `toContain("1 материал")`
 * проходил и на «1 материалов» — тест был зелёным при ровно той ошибке,
 * которую сторожил. Вскрыто проверкой внесёнными дефектами.
 */
describe("подвал склоняет существительное при числе", () => {
  it("товары — «1 наименование»", () => {
    const totals = productTotals({
      quantity: "1.000",
      free_quantity: "0.000",
      revenue_kopecks: 10000,
      documents_count: 1,
      products_count: 1,
      revenue_share: "1.00000000",
    })

    expect(String(totals.label)).toMatch(/· 1 наименование$/)
  })

  it("приёмки — «1 материал»", () => {
    const totals = supplyTotals({
      materials_count: 1,
      amount_kopecks: 250500,
      amount_share: "1.00000000",
      priced_count: 1,
      unpriced_count: 0,
      documents_count: 1,
      suppliers_count: 1,
    })

    expect(String(totals.label)).toMatch(/· 1 материал$/)
  })

  it("материалы — «1 материал»", () => {
    const totals = materialTotals({
      materials_count: 1,
      cost_kopecks: 1250,
      cost_share: "1.00000000",
      priced_count: 1,
      unpriced_count: 0,
    })

    expect(String(totals.label)).toMatch(/· 1 материал$/)
  })
})
