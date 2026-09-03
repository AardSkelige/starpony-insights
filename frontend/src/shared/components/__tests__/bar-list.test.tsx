import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { BarList, type Bar } from "@/shared/components/bar-list"

/**
 * Полоса не имеет права быть длиннее, чем её величина.
 *
 * Дефект жил в общем компоненте и врал ровно наоборот: `width: -38%` —
 * невалидное объявление, браузер выбрасывает его целиком, и заливка,
 * будучи блоком внутри дорожки, растягивается **во всю длину**. Убыточная
 * линейка рисовалась самой длинной в списке и читалась как лучшая.
 *
 * Ни консоль, ни типы этого не ловят: значение приходит числом, стиль
 * собирается строкой. Проверяется рендером — иначе клампинг однажды
 * уберут как «лишний».
 */
function fills(container: HTMLElement): string[] {
  return [...container.querySelectorAll(".motion-bar-reveal")].map(
    (node) => (node as HTMLElement).style.width
  )
}

const BARS: Bar[] = [
  { key: "good", label: "Прибыльная", value: 78, display: "78,0 %" },
  { key: "bad", label: "Убыточная", value: -30, display: "−30,0 %" },
]

describe("BarList", () => {
  it("отдаёт браузеру валидную ширину, а не отброшенное объявление", () => {
    // Проверяется именно **валидность**, а не знак: и jsdom, и браузер
    // выбрасывают `width: -38%` целиком, и свойство становится пустым.
    // «Не начинается с минуса» проходило бы и на сломанном коде — этот
    // тест на том и был пойман проверкой на покраснение. Пустая ширина
    // означает заливку во всю дорожку.
    const { container } = render(<BarList bars={BARS} />)

    for (const width of fills(container)) {
      expect(width, "ширина отброшена браузером — полоса растянется во всю дорожку")
        .toMatch(/^\d+(\.\d+)?%$/)
    }
  })

  it("убыточная полоса короче прибыльной, а не длиннее", () => {
    const { container } = render(<BarList bars={BARS} />)
    const [good, bad] = fills(container).map((width) => parseFloat(width) || 0)

    expect(bad).toBeLessThan(good)
  })

  it("масштаб считается по положительным величинам", () => {
    // Иначе одна отрицательная величина, оказавшаяся наибольшей по модулю,
    // сжимала бы весь список в кромку.
    const { container } = render(<BarList bars={BARS} />)

    expect(fills(container)[0]).toBe("100%")
  })
})
