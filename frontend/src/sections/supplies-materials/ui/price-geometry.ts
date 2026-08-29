import type { PricePoint } from "@/sections/supplies-materials/api"
import { formatDate, formatUnitPrice } from "@/shared/lib/format"

/**
 * Геометрия линии закупочных цен — отдельно от рисования.
 *
 * Здесь ошибка тихая: линия не падает и не выглядит сломанной, она просто
 * показывает не тот тренд. Поэтому расчёт живёт чистой функцией и покрыт
 * тестами, а компонент только рисует то, что она вернула.
 *
 * Координаты считаются **в точках**, а не в условных единицах viewBox:
 * растягивание viewBox по ширине превращает круглые точки в эллипсы,
 * а линию делает разной толщины по вертикали и горизонтали.
 */
export type Dot = { x: number; y: number; point: PricePoint }
export type Geometry = { points: string; dots: Dot[] }

/**
 * Точки в координатах вида. `null` — рисовать нечего.
 *
 * **По времени, а не по номеру закупки.** Между 28.02 и 14.05 два с половиной
 * месяца, между 01.07 и 30.07 — один. Равные промежутки соврали бы о том,
 * как быстро материал дорожает, — а вопрос страницы именно в этом.
 *
 * **Ось цены не начинается с нуля намеренно.** Вопрос страницы — «на сколько
 * изменилось», и растянутый до нуля график превратил бы рост на 16 %
 * в незаметную рябь у верхней кромки. У линии базовая точка не ноль,
 * а предыдущая цена; у столбиков было бы наоборот.
 *
 * **Меньше двух точек линии нет.** У 130 наименований из 212 закупка была
 * одна, у 24 цены нет вовсе: одинокая точка читалась бы как начало тренда,
 * которого не существует.
 */
export function geometry(
  prices: PricePoint[],
  width: number,
  height: number,
  pad: number
): Geometry | null {
  if (prices.length < 2 || width <= 0) return null

  const values = prices.map((point) => Number(point.price_kopecks))
  const times = prices.map((point) => new Date(point.moment).getTime())

  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const minTime = Math.min(...times)
  const maxTime = Math.max(...times)

  // Цена не менялась ни разу — таких десять. Прямая посередине, а не по верхней
  // кромке: у кромки она читалась бы как «цена на максимуме».
  const flat = maxValue === minValue
  const valueSpan = maxValue - minValue
  // Все закупки одним моментом — линия по времени вырождается в точку.
  // Тогда точки раскладываются по порядку: «времени между ними нет,
  // покажем как есть». Делить на нуль нельзя — обе точки легли бы в нуль,
  // и вместо линии получился бы отрезок нулевой длины.
  const instant = maxTime === minTime
  const timeSpan = maxTime - minTime
  const plot = height - pad * 2
  const steps = prices.length - 1

  // Точка не должна упираться в края: её радиус вылез бы за рисунок,
  // и первая с последней оказались бы срезанными.
  const span = width - pad * 2

  const dots = prices.map((point, index) => ({
    x: round(
      pad +
        (instant
          ? (index / steps) * span
          : ((times[index] - minTime) / timeSpan) * span)
    ),
    y: round(
      flat ? height / 2 : pad + ((maxValue - values[index]) / valueSpan) * plot
    ),
    point,
  }))

  return {
    points: dots.map((dot) => `${dot.x},${dot.y}`).join(" "),
    dots,
  }
}

function round(value: number): number {
  return Math.round(value * 10) / 10
}

/**
 * Что читает экранный диктор и что видит тот, кому линия не помогает.
 *
 * Обязательна: линия — единственный носитель тренда в колонке, и без подписи
 * колонка для чтения с экрана пуста.
 */
export function describe(prices: PricePoint[]): string {
  const first = prices[0]
  const last = prices[prices.length - 1]
  return (
    `Цена закупки: ${formatUnitPrice(first.price_kopecks)} ` +
    `${formatDate(first.moment)} → ${formatUnitPrice(last.price_kopecks)} ` +
    `${formatDate(last.moment)}, закупок ${prices.length}`
  )
}


/**
 * С какой стороны от точки раскрыть подсказку при наведении.
 *
 * Считается по трети ширины, а не по измеренной ширине подсказки: в левой
 * трети места вправо хватает заведомо, в правой — влево, а посередине
 * безопасно центрировать. Мерить подсказку значило бы рисовать её сначала
 * не на месте, а потом сдвигать — заметный скачок при каждом наведении.
 *
 * Центрированная у краёв подсказка уезжает за рисунок, и таблица со своей
 * горизонтальной прокруткой её обрезает: у первой точки «04.03.2026 ·
 * 7,57 ₽/шт» превращалось в «2026 · 7,57 ₽/шт».
 */
export type Anchor = "start" | "center" | "end"

export function anchorOf(x: number, width: number): Anchor {
  if (x < width / 3) return "start"
  if (x > (width * 2) / 3) return "end"
  return "center"
}
