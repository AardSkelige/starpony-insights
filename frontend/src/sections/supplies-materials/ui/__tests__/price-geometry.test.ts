import { describe as suite, expect, it } from "vitest"

import {
  anchorOf,
  describe,
  geometry,
} from "@/sections/supplies-materials/ui/price-geometry"

/** Момент в московском поясе — в нём живёт учёт. */
function at(day: string, price: string) {
  return { moment: `${day}T12:00:00+03:00`, price_kopecks: price }
}

/** Изопропиловый спирт с боевых: шесть закупок, скачок в середине. */
const SPIRIT = [
  at("2026-02-28", "24.91"),
  at("2026-05-14", "24.00"),
  at("2026-06-10", "30.00"),
  at("2026-07-01", "24.00"),
  at("2026-07-30", "22.02"),
  at("2026-08-10", "24.00"),
]

suite("линия закупочных цен", () => {
  suite("когда рисовать нечего", () => {
    it("одна закупка — линии нет", () => {
      // У 130 наименований из 212 закупка одна. Одинокая точка читалась бы
      // как начало тренда, которого не существует.
      expect(geometry([at("2026-04-09", "82.55")], 56, 16, 2)).toBeNull()
    })

    it("ни одной цены — линии нет", () => {
      // 24 наименования приходили только даром.
      expect(geometry([], 56, 16, 2)).toBeNull()
    })
  })

  suite("горизонталь — время, а не номер закупки", () => {
    it("промежутки пропорциональны датам", () => {
      // Между 01.01 и 01.02 месяц, между 01.02 и 01.03 — тоже; а вот
      // 01.01 → 01.02 → 01.07 равными быть не должны.
      const shape = geometry(
        [at("2026-01-01", "10"), at("2026-02-01", "20"), at("2026-07-01", "30")],
        100,
        20,
        0
      )!

      const [first, second, third] = shape.dots
      expect(first.x).toBe(0)
      expect(third.x).toBe(100)
      // 31 день из 181 — примерно шестая часть, а не половина.
      expect(second.x).toBeCloseTo(17.1, 0)
      expect(second.x).toBeLessThan(30)
    })

    it("две закупки одним днём не роняют расчёт", () => {
      // Делить на ноль нельзя; точки должны лечь по краям.
      const shape = geometry(
        [at("2026-06-01", "10"), at("2026-06-01", "20")],
        100,
        20,
        0
      )!

      expect(shape.dots.map((dot) => dot.x)).toEqual([0, 100])
    })

    it("первая точка слева, последняя справа", () => {
      const shape = geometry(SPIRIT, 300, 80, 9)!
      expect(shape.dots[0].x).toBe(9)
      expect(shape.dots[5].x).toBe(291)
    })

    it("крайние точки отступают от краёв на свой радиус", () => {
      // Без отступа круг первой точки срезается пополам левым краем
      // рисунка, и линия выглядит начатой из ниоткуда.
      const pad = 10
      const shape = geometry(SPIRIT, 300, 80, pad)!

      for (const dot of shape.dots) {
        expect(dot.x).toBeGreaterThanOrEqual(pad)
        expect(dot.x).toBeLessThanOrEqual(300 - pad)
      }
    })

    it("нулевая ширина — рисовать нечего", () => {
      // Первый кадр до измерения контейнера. Рисовать по догадке нельзя:
      // она даст скачок при первом же измерении.
      expect(geometry(SPIRIT, 0, 80, 9)).toBeNull()
    })
  })

  suite("вертикаль — цена, и ноль в ней не участвует", () => {
    it("самая дорогая закупка у верхней кромки, самая дешёвая у нижней", () => {
      // Ось не растянута до нуля намеренно: вопрос страницы — «на сколько
      // изменилось», и до нуля рост на 16 % стал бы незаметной рябью.
      const shape = geometry(SPIRIT, 300, 80, 10)!

      // 30,00 — максимум ряда, 22,02 — минимум.
      expect(shape.dots[2].y).toBe(10)
      expect(shape.dots[4].y).toBe(70)
    })

    it("равные цены дают равные высоты", () => {
      const shape = geometry(SPIRIT, 300, 80, 10)!
      // Три закупки по 24,00 ₽ обязаны лежать на одной высоте.
      expect(shape.dots[1].y).toBe(shape.dots[3].y)
      expect(shape.dots[3].y).toBe(shape.dots[5].y)
    })

    it("выше цена — выше точка", () => {
      const shape = geometry(SPIRIT, 300, 80, 10)!
      // 24,91 дороже 24,00, значит лежит выше — то есть y меньше.
      expect(shape.dots[0].y).toBeLessThan(shape.dots[1].y)
    })

    it("ровная цена — прямая посередине, а не по кромке", () => {
      // Таких материалов десять. У верхней кромки прямая читалась бы
      // как «цена на максимуме».
      const shape = geometry(
        [at("2026-05-01", "45"), at("2026-06-01", "45")],
        100,
        80,
        10
      )!

      expect(shape.dots.map((dot) => dot.y)).toEqual([40, 40])
    })
  })

  suite("точка несёт свою закупку", () => {
    it("к каждой точке приложена та закупка, из которой она получена", () => {
      // Подсказка при наведении берёт дату и цену отсюда. Разойдись
      // порядок — курсор показывал бы цену соседней закупки.
      const shape = geometry(SPIRIT, 300, 80, 9)!
      expect(shape.dots.map((dot) => dot.point.price_kopecks)).toEqual(
        SPIRIT.map((point) => point.price_kopecks)
      )
    })
  })

  suite("строка точек", () => {
    it("совпадает с самими точками", () => {
      // Расхождение здесь нарисовало бы линию не через свои же точки.
      const shape = geometry(SPIRIT, 300, 80, 9)!
      expect(shape.points).toBe(
        shape.dots.map((dot) => `${dot.x},${dot.y}`).join(" ")
      )
    })

    it("точек столько же, сколько закупок", () => {
      const shape = geometry(SPIRIT, 300, 80, 9)!
      expect(shape.dots).toHaveLength(SPIRIT.length)
    })
  })
})

suite("подпись линии для чтения с экрана", () => {
  it("называет крайние цены, их даты и число закупок", () => {
    // Линия — единственный носитель тренда в колонке. Без подписи колонка
    // для экранного диктора пуста.
    const text = describe(SPIRIT)

    // Три значащие цифры: цена 0,2491 ₽/г показывается как «0,249»,
    // а не «0,25» — иначе умножение на количество не сходится с суммой.
    expect(text).toContain("0,249")
    expect(text).toContain("28.02.2026")
    expect(text).toContain("10.08.2026")
    expect(text).toContain("закупок 6")
  })
})


suite("сторона подсказки при наведении", () => {
  it("у левых точек раскрывается вправо", () => {
    // Центрированная у края, она уезжает за рисунок, а таблица со своей
    // горизонтальной прокруткой обрезает: «04.03.2026 · 7,57 ₽/шт»
    // превращалось в «2026 · 7,57 ₽/шт».
    expect(anchorOf(0, 600)).toBe("start")
    expect(anchorOf(10, 600)).toBe("start")
  })

  it("у правых точек раскрывается влево", () => {
    expect(anchorOf(600, 600)).toBe("end")
    expect(anchorOf(590, 600)).toBe("end")
  })

  it("в середине центрируется", () => {
    expect(anchorOf(300, 600)).toBe("center")
  })

  it("крайние точки графика никогда не центрируются", () => {
    // Проверяется на настоящей геометрии, а не на числах из головы:
    // отступ краёв меняли, и проверка должна ломаться вместе с ним.
    const width = 600
    const shape = geometry(SPIRIT, width, 96, 10)!
    const first = shape.dots[0]
    const last = shape.dots[shape.dots.length - 1]

    expect(anchorOf(first.x, width)).toBe("start")
    expect(anchorOf(last.x, width)).toBe("end")
  })
})
