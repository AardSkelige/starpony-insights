import { describe, expect, it } from "vitest"

import { splitNavigation } from "@/app/layout/nav-groups"
import type { Page } from "@/shared/api/client"

const page = (key: string, group: string, label = key): Page => ({
  key,
  label,
  group,
  route: `/${key}`,
})

describe("splitNavigation", () => {
  it("пункт без группы уходит наверх", () => {
    const { top, groups } = splitNavigation([page("home", ""), page("suppliers", "Склад")])
    expect(top.map((p) => p.key)).toEqual(["home"])
    expect(groups).toHaveLength(1)
  })

  it("сохраняет порядок групп и пунктов с сервера", () => {
    // Порядок — не косметика: он совпадает с админкой доступов, где по тем же
    // группам выдаются права. Разойдутся — человек будет искать пункт не там.
    const { groups } = splitNavigation([
      page("suppliers", "Склад"),
      page("deadlines", "Деньги"),
      page("inventory", "Склад"),
    ])
    expect(groups.map((g) => g.label)).toEqual(["Склад", "Деньги"])
    expect(groups[0].pages.map((p) => p.key)).toEqual(["suppliers", "inventory"])
  })

  it("пустой список не ломает раскладку", () => {
    expect(splitNavigation([])).toEqual({ top: [], groups: [] })
  })

  it("человеку с одним разделом показывается только он", () => {
    // Меню строится из ответа сервера: что не выдано — не появляется.
    const { top, groups } = splitNavigation([page("deadlines", "Деньги")])
    expect(top).toEqual([])
    expect(groups).toHaveLength(1)
    expect(groups[0].pages).toHaveLength(1)
  })
})
