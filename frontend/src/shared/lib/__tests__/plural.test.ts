import { describe, expect, it } from "vitest"

import { plural, withPlural } from "@/shared/lib/plural"

const FORMS = ["изделие", "изделия", "изделий"] as const

describe("plural", () => {
  it("склоняет по последней цифре", () => {
    expect(plural(1, ...FORMS)).toBe("изделие")
    expect(plural(2, ...FORMS)).toBe("изделия")
    expect(plural(5, ...FORMS)).toBe("изделий")
    expect(plural(21, ...FORMS)).toBe("изделие")
    expect(plural(43, ...FORMS)).toBe("изделия")
  })

  it("знает про одиннадцать–четырнадцать", () => {
    // Они кончаются на 1–4, но склоняются как «много». Без этого
    // интерфейс говорит «11 изделие» — первое, что замечают в готовой странице.
    for (const count of [11, 12, 13, 14, 111, 112]) {
      expect(plural(count, ...FORMS)).toBe("изделий")
    }
  })

  it("считает ноль многим", () => {
    expect(plural(0, ...FORMS)).toBe("изделий")
  })

  it("собирает число со словом", () => {
    expect(withPlural(39, ...FORMS)).toBe("39 изделий")
  })
})
