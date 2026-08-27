import { describe, expect, it } from "vitest"

import { cn } from "@/shared/lib/utils"

describe("cn", () => {
  it("склеивает классы", () => {
    expect(cn("px-2", "py-1")).toBe("px-2 py-1")
  })

  it("последний конфликтующий класс побеждает", () => {
    // Ради этого cn и существует: без tailwind-merge в разметке остались бы
    // оба класса, и какой победит — решал бы порядок в CSS, а не в коде.
    expect(cn("bg-primary", "bg-muted")).toBe("bg-muted")
  })

  it("отбрасывает ложные значения", () => {
    const hidden = false
    expect(cn("px-2", hidden && "hidden", undefined)).toBe("px-2")
  })
})
