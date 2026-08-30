import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { CoverageSection } from "@/shared/components/detail/coverage"

/**
 * Прочерк у запаса бывает по двум разным причинам, и путать их нельзя.
 *
 * `days_left === null` приходит и когда остатка нет в отчёте МойСклада,
 * и когда остаток известен, но за период материал не расходовался — делить
 * не на что. Раньше оба случая печатали «остатка в отчёте нет», и во втором
 * это было прямой ложью об учёте: остаток как раз известен.
 *
 * Проверяется рендером, а не чтением исходников: различие живёт в ветке
 * разметки, и опечатка в условии вернула бы старое поведение молча.
 */
function detail(
  coverage: Partial<{ days_left: number | null; per_day: string; level: string }>,
  stock: { available: string } | null
) {
  return {
    isPending: false,
    isError: false,
    refetch: () => {},
    data: {
      coverage: {
        quantity: "0.000",
        per_day: "0.000",
        days_of_period: 30,
        days_left: null,
        level: "none",
        ...coverage,
      },
      stock,
    },
  }
}

describe("запас: прочерк объясняет свою причину", () => {
  it("остатка нет в отчёте — так и сказано", () => {
    render(
      <CoverageSection
        detail={detail({ per_day: "12.900" }, null) as never}
        uom="шт"
      />
    )

    expect(screen.getByText(/в отчёте МойСклада нет/)).toBeInTheDocument()
    expect(screen.queryByText(/не расходовался/)).not.toBeInTheDocument()
  })

  it("остаток есть, а расхода не было — про остаток не врём", () => {
    render(
      <CoverageSection
        detail={detail({ per_day: "0.000" }, { available: "989.000" }) as never}
        uom="шт"
      />
    )

    expect(screen.getByText(/не расходовался/)).toBeInTheDocument()
    // Главное: старое сообщение здесь было ложью — остаток известен.
    expect(screen.queryByText(/в отчёте МойСклада нет/)).not.toBeInTheDocument()
  })

  it("нулевой расход не выдаётся за измеренный", () => {
    render(
      <CoverageSection
        detail={detail({ per_day: "0.000" }, null) as never}
        uom="шт"
      />
    )

    // «Расход известен — 0 шт в день» описывает расход, которого не считали.
    expect(screen.queryByText(/Расход известен/)).not.toBeInTheDocument()
  })
})
