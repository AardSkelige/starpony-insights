import { describe, expect, it } from "vitest"

import { withQuery, withSelection } from "@/shared/api/table-query"

const EMPTY = {
  dateFrom: null,
  dateTo: null,
  channelId: null,
  search: "",
  page: 1,
}

describe("адрес запроса таблицы", () => {
  it("без выбранного — чистый путь", () => {
    // Иначе «?» висит в конце каждой ссылки, которую человек пересылает.
    expect(withQuery("/api/shipments/products/", EMPTY)).toBe(
      "/api/shipments/products/"
    )
  })

  it("умолчания в адрес не попадают", () => {
    // Первая страница и пустой поиск — это «ничего не выбрано». Написать
    // их явно значит замусорить ссылку тем, о чём человек не просил.
    expect(withQuery("/x/", { ...EMPTY, page: 1, search: "" })).toBe("/x/")
  })

  it("выбранное попадает целиком", () => {
    const url = withQuery("/x/", {
      dateFrom: "2026-06-01",
      dateTo: "2026-06-30",
      channelId: 7,
      search: "вода",
      page: 3,
      ordering: "-cost",
      pageSize: 25,
    })

    expect(url).toContain("date_from=2026-06-01")
    expect(url).toContain("date_to=2026-06-30")
    expect(url).toContain("channel_id=7")
    expect(url).toContain("page=3")
    expect(url).toContain("ordering=-cost")
    expect(url).toContain("page_size=25")
  })

  it("поиск экранируется", () => {
    // Артикулы содержат «+» и пробелы, а незакодированный «+» приезжает
    // на сервер пробелом — и строка не находится.
    const url = withQuery("/x/", { ...EMPTY, search: "шампунь 500+" })

    expect(url).toContain("search=%D1%88")
    expect(url).not.toContain(" ")
    expect(url).toContain("%2B")
  })

  it("выборка без страницы не тащит номер страницы", () => {
    // Выгрузка и детали строки описывают всю выборку. Приедь сюда «страница
    // третья» — файл содержал бы третью сотню строк вместо всех.
    const url = withSelection("/x/xlsx/", {
      ...EMPTY,
      search: "вода",
      ordering: "-cost",
    })

    expect(url).not.toContain("page=")
    expect(url).toContain("search=")
  })
})
