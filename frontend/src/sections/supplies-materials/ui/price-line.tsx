import * as React from "react"

import type { PricePoint } from "@/sections/supplies-materials/api"
import {
  anchorOf,
  describe,
  geometry,
} from "@/sections/supplies-materials/ui/price-geometry"
import { useElementWidth } from "@/shared/hooks/use-element-width"
import { formatDate, formatUnitPrice } from "@/shared/lib/format"
import { cn } from "@/shared/lib/utils"

/**
 * Ряд закупочных цен линией: микро-линия в ячейке и график в разборе.
 *
 * **Один ряд — легенды не нужно**, колонка его и называет; цвет поэтому
 * `primary`, а не `--chart-1`: категориальный слот отвечает на «какая
 * из серий», а различать здесь нечего (`DESIGN.md` §1, «Графики»).
 *
 * **Рисуется в точках, а не в растянутом viewBox.** `preserveAspectRatio="none"`
 * выглядел проще — задал `viewBox="0 0 300 80"` и растянул, — но растягивает
 * он вместе с координатами всё: точки превращались в эллипсы, а линия была
 * толще по вертикали, чем по горизонтали. При ширине 1170 против 300
 * это четырёхкратное искажение.
 *
 * Расчёт точек — в `price-geometry.ts`: там ошибка тихая (линия показывает
 * не тот тренд, не падая), и он покрыт тестами. Здесь только рисование.
 */
const SPARK_WIDTH = 56
const SPARK_HEIGHT = 16

/** Микро-линия в ячейке таблицы. Подписей нет — они в соседней ячейке. */
export function PriceSpark({ prices }: { prices: PricePoint[] }) {
  // Ширина фиксированная, растягивать нечего — измерять тоже нечего.
  const shape = geometry(prices, SPARK_WIDTH, SPARK_HEIGHT, 2.5)

  if (!shape) {
    // Место занято всегда, чтобы цены в колонке стояли в один столбец.
    // Точка, а не пустота: пустота читается как «не загрузилось».
    return (
      <span
        aria-hidden
        className="inline-block w-14 shrink-0 text-center text-muted-foreground"
      >
        ·
      </span>
    )
  }

  const last = shape.dots[shape.dots.length - 1]

  return (
    <svg
      width={SPARK_WIDTH}
      height={SPARK_HEIGHT}
      viewBox={`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`}
      role="img"
      aria-label={describe(prices)}
      className="shrink-0"
    >
      <polyline
        points={shape.points}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Последняя точка помечена: колонка отвечает «почём сейчас»,
          и глаз должен находить конец линии, а не её середину. */}
      <circle cx={last.x} cy={last.y} r="2" fill="var(--primary)" />
    </svg>
  )
}

const CHART_HEIGHT = 96
const CHART_PAD = 10

/**
 * График истории цен в разборе строки.
 *
 * **Живой, а не картинка.** Наведи курсор на точку — увидишь дату, цену
 * и поставщика; это правило скила `dataviz`: у линии слой наведения
 * по умолчанию, а не по желанию. Без него график сообщает форму, но не даёт
 * прочесть ни одного значения, кроме крайних.
 *
 * Подписаны только крайние точки: число на каждой — шум, за которым
 * перестают видеть саму линию.
 */
export function PriceChart({
  prices,
  uom,
}: {
  prices: PricePoint[]
  /** Единица измерения: цена показывается «за грамм», а не просто «₽». */
  uom?: string
}) {
  const { ref, width } = useElementWidth<HTMLDivElement>()
  const [hovered, setHovered] = React.useState<number | null>(null)

  const shape = width ? geometry(prices, width, CHART_HEIGHT, CHART_PAD) : null

  if (prices.length < 2) return null

  const first = prices[0]
  const last = prices[prices.length - 1]
  const active = hovered !== null && shape ? shape.dots[hovered] : null

  return (
    <figure className="m-0 flex min-w-0 flex-col gap-1">
      {/* Обёртка меряется, SVG рисуется по её ширине: масштаб 1:1,
          и ничто не растягивается. */}
      <div ref={ref} className="relative w-full" style={{ height: CHART_HEIGHT }}>
        {shape ? (
          <svg
            width={width!}
            height={CHART_HEIGHT}
            role="img"
            aria-label={describe(prices)}
            className="block"
            onMouseLeave={() => setHovered(null)}
          >
            {/* Сетка приглушена: она подпорка, а не содержание. */}
            <line
              x1="0"
              y1={CHART_PAD}
              x2={width!}
              y2={CHART_PAD}
              stroke="var(--border)"
            />
            <line
              x1="0"
              y1={CHART_HEIGHT - CHART_PAD}
              x2={width!}
              y2={CHART_HEIGHT - CHART_PAD}
              stroke="var(--border)"
            />

            {active ? (
              <line
                x1={active.x}
                y1="0"
                x2={active.x}
                y2={CHART_HEIGHT}
                stroke="var(--muted-foreground)"
                strokeDasharray="3 3"
              />
            ) : null}

            <polyline
              points={shape.points}
              fill="none"
              stroke="var(--primary)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {shape.dots.map((dot, index) => (
              <circle
                key={index}
                cx={dot.x}
                cy={dot.y}
                r={index === shape.dots.length - 1 || index === hovered ? 4 : 3}
                fill={
                  index === shape.dots.length - 1 || index === hovered
                    ? "var(--primary)"
                    : "var(--background)"
                }
                stroke="var(--primary)"
                strokeWidth="2"
              />
            ))}

            {/* Прозрачные накладки шире самих точек: попасть курсором
                в круг радиусом три точки нельзя. Правило `dataviz` —
                цель наведения больше метки. */}
            {shape.dots.map((dot, index) => (
              <circle
                key={`hit-${index}`}
                cx={dot.x}
                cy={dot.y}
                r="14"
                fill="transparent"
                onMouseEnter={() => setHovered(index)}
              />
            ))}
          </svg>
        ) : null}

        {/* Подсказка — обычным HTML поверх, а не `<text>` в SVG: перенос,
            табличные цифры и токены темы там работают как везде.

            **Сторона выбирается по положению точки.** Центрированная
            по краям она уезжает за рисунок, и таблица со своей
            горизонтальной прокруткой её обрезает: у первой точки
            «04.03.2026 · 7,57 ₽/шт» превращалось в «2026 · 7,57 ₽/шт».
            Слева раскрывается вправо, справа — влево, в середине
            по центру. Ширину подсказки при этом знать не нужно. */}
        {active ? (
          <div
            role="status"
            className={cn(
              "pointer-events-none absolute z-10 rounded-md bg-primary px-2 py-1 text-xs whitespace-nowrap text-primary-foreground shadow-sm tabular-nums",
              anchorOf(active.x, width!) === "center" && "-translate-x-1/2",
              anchorOf(active.x, width!) === "end" && "-translate-x-full"
            )}
            style={{
              left: active.x,
              // Над точкой, а у самого верха — под ней: иначе подсказка
              // уезжает за верхний край рисунка и обрезается.
              top: active.y < 34 ? active.y + 12 : active.y - 30,
            }}
          >
            {formatDate(active.point.moment)} ·{" "}
            {formatUnitPrice(active.point.price_kopecks)}
            {uom ? `/${uom}` : ""}
          </div>
        ) : null}
      </div>

      {/* Крайние значения — обычным текстом под графиком. */}
      <figcaption className="flex items-baseline justify-between gap-3 text-xs text-muted-foreground tabular-nums">
        <span className="shrink-0">
          {formatUnitPrice(first.price_kopecks)} · {formatDate(first.moment)}
        </span>
        <span className="shrink-0">
          {formatUnitPrice(last.price_kopecks)} · {formatDate(last.moment)}
        </span>
      </figcaption>
    </figure>
  )
}
