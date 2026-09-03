import { describe, expect, it } from "vitest"

import type { ProductRow } from "@/sections/production/api"
import { runningOut } from "@/sections/production/running-out"
import {
  MAX_QUANTITY,
  parseBatch,
  serialiseBatch,
  withAllSuggested,
} from "@/sections/production/use-batch"

/**
 * Партия в адресной строке: что проставила страница, а что человек.
 *
 * Различие тихое и потому опасное. Пока его не было, «Взять всё» записывало
 * в адрес числа — и переключатель горизонта 30/60/90 переставал на них
 * действовать: страница выглядела сломанной, хотя послушно не трогала
 * «введённое руками», которого человек не вводил.
 *
 * Ошибка здесь не падает: партия считается, числа правдоподобны, просто
 * переключатель молча ничего не меняет.
 */

function row(
  article: string,
  suggested: number | null,
  extra: Partial<ProductRow> = {}
): ProductRow {
  return {
    product_id: 1,
    article,
    name: article,
    folder: "",
    uom: "шт",
    available: "0.000",
    coverage: {
      quantity: "0.000",
      per_day: "0.000",
      days_of_period: 30,
      days_left: 0,
      level: "critical",
    },
    suggested,
    horizon: 60,
    has_plan: true,
    ...extra,
  } as ProductRow
}

describe("разбор партии из адреса", () => {
  it("артикул без количества — «сколько предложит страница»", () => {
    expect(parseBatch("200.001.05")).toEqual({ "200.001.05": null })
  })

  it("артикул с количеством — закреплено руками", () => {
    expect(parseBatch("200.001.05:12")).toEqual({ "200.001.05": 12 })
  })

  it("оба вида в одной ссылке", () => {
    expect(parseBatch("200.001.05,200.037.05:120")).toEqual({
      "200.001.05": null,
      "200.037.05": 120,
    })
  })

  it("пустое и мусорное не роняют остальное", () => {
    // Ссылку правят руками, и опечатка в конце адреса не должна стоить
    // человеку всего, что он набрал.
    expect(parseBatch(null)).toEqual({})
    expect(parseBatch("200.001.05,,200.037.05:0")).toEqual({
      "200.001.05": null,
    })
  })

  it("количество длиннее семи цифр в адрес не проходит", () => {
    // Потолок общий с сервером. Без него восьмая цифра ломала бы разбор,
    // и позиция исчезала бы из партии в момент набора.
    expect(parseBatch("200.001.05:12345678")).toEqual({})
    expect(parseBatch("200.001.05:1234567")).toEqual({ "200.001.05": 1234567 })
  })
})

describe("запись партии в адрес", () => {
  it("несвязанное количество пишется голым артикулом", () => {
    expect(serialiseBatch({ "200.001.05": null })).toBe("200.001.05")
  })

  it("закреплённое пишется с числом", () => {
    expect(serialiseBatch({ "200.001.05": 12 })).toBe("200.001.05:12")
  })

  it("пустая партия не оставляет следа в адресе", () => {
    expect(serialiseBatch({})).toBeNull()
  })

  it("разбор и запись сходятся обратно", () => {
    const url = "200.001.05,200.037.05:120"
    expect(serialiseBatch(parseBatch(url))).toBe(url)
  })
})

/**
 * Разрешение количеств здесь не проверяется — его здесь и нет.
 *
 * Оно переехало на сервер (`api/production/services/payload.py::resolve`),
 * и это не перестановка кода: на фронте оно опиралось на список товаров,
 * а тот приходит суженным поиском — партия молча теряла всё, чего
 * в найденном не оказалось. Проверки живут рядом с расчётом:
 * `tests/production/test_api.py::TestSuggestedInBatch`.
 */

describe("«Взять всё, что кончается»", () => {
  const rows = [row("200.001.05", 8), row("200.037.05", 33), row("100.022.03", null)]

  it("кладёт связь с горизонтом, а не число", () => {
    // Иначе переключатель 30/60/90 после нажатия перестаёт что-либо менять.
    expect(withAllSuggested({}, rows)).toEqual({
      "200.001.05": null,
      "200.037.05": null,
    })
  })

  it("не стирает закреплённое руками", () => {
    expect(withAllSuggested({ "200.001.05": 120 }, rows)).toEqual({
      "200.001.05": 120,
      "200.037.05": null,
    })
  })

  it("товар без предложения не берёт", () => {
    expect(withAllSuggested({}, [row("100.022.03", null)])).toEqual({})
  })
})


describe("что требует решения", () => {
  const urgent = row("200.001.05", 8)
  const calm = row("400.003.15", 1, {
    coverage: {
      quantity: "3.000",
      per_day: "0.033",
      days_of_period: 90,
      days_left: 568,
      level: "ok",
    },
  })
  const unknown = row("100.020.03", null, {
    available: null,
    coverage: {
      quantity: "0.000",
      per_day: "0.000",
      days_of_period: 90,
      days_left: null,
      level: "none",
    },
  })

  it("кончающееся входит, спокойное нет", () => {
    expect(runningOut([urgent, calm], {}).map((r) => r.article)).toEqual([
      "200.001.05",
    ])
  })

  it("неизвестный остаток входит", () => {
    // Кнопка обещает про скрытые «их пока хватает», а про эти мы не знаем.
    expect(runningOut([calm, unknown], {}).map((r) => r.article)).toEqual([
      "100.020.03",
    ])
  })

  it("уже отмеченное остаётся на виду", () => {
    expect(
      runningOut([calm], { "400.003.15": 12 }).map((r) => r.article)
    ).toEqual(["400.003.15"])
  })

  it("«Взять всё» берёт только это, а не весь каталог", () => {
    // До этого кнопка складывала в партию все строки с предложением,
    // включая спрятанные за «их пока хватает».
    const rows = [urgent, calm, unknown]
    expect(withAllSuggested({}, runningOut(rows, {}))).toEqual({
      "200.001.05": null,
    })
    expect(Object.keys(withAllSuggested({}, rows))).toHaveLength(2)
  })
})

describe("потолок количества", () => {
  it("общий с сервером и с разбором адреса", () => {
    expect(MAX_QUANTITY).toBe(9_999_999)
    expect(parseBatch(`200.001.05:${MAX_QUANTITY}`)).toEqual({
      "200.001.05": MAX_QUANTITY,
    })
    expect(parseBatch(`200.001.05:${MAX_QUANTITY + 1}`)).toEqual({})
  })
})
