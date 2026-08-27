import { describe, expect, it } from "vitest"

import { pagesToShow } from "@/shared/lib/pagination"

describe("pagesToShow", () => {
  it("показывает все номера, пока их мало", () => {
    expect(pagesToShow(1, 3)).toEqual([1, 2, 3])
  })

  it("прячет середину за многоточием", () => {
    // Полоса из двадцати кнопок не помещается на экране, а нужны только
    // края и окрестность текущей страницы.
    expect(pagesToShow(10, 20)).toEqual([1, null, 9, 10, 11, null, 20])
  })

  it("не ставит многоточие ради одного пропущенного номера", () => {
    // «1 … 3 4 5» занимает столько же места, сколько «1 2 3 4 5»,
    // но по многоточию нельзя нажать.
    expect(pagesToShow(4, 5)).toEqual([1, 2, 3, 4, 5])
    expect(pagesToShow(3, 5)).toEqual([1, 2, 3, 4, 5])
  })

  it("не выходит за границы", () => {
    // Пропущены два номера — многоточие на месте.
    expect(pagesToShow(1, 5)).toEqual([1, 2, null, 5])
    expect(pagesToShow(5, 5)).toEqual([1, null, 4, 5])
  })

  it("не повторяет номер, попавший сразу в два правила", () => {
    // Первая страница она же текущая — кнопка должна быть одна.
    expect(pagesToShow(1, 1)).toEqual([1])
    expect(pagesToShow(2, 2)).toEqual([1, 2])
  })
})
