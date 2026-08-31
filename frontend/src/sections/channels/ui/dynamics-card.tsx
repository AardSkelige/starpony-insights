import * as React from "react"

import type { Dynamics } from "@/sections/channels/api"
import { slotColor } from "@/sections/channels/api"
import { bucketLabel, formatDay, stepNote } from "@/sections/channels/bucket"
import { Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatMoney } from "@/shared/lib/format"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

/**
 * Выручка по каналам во времени — ряд на канал, а не стопка.
 *
 * **Стопка отвечала на «сколько всего» и молчала о том, зачем её открывают.**
 * Двадцать два столбика, в каждом шесть сегментов: чтобы понять, растёт ли
 * Озон, приходилось выискивать зелёную прослойку в каждом столбике и держать
 * в голове её толщину. Вопрос же к этому блоку — **кто растёт, а кто
 * заглох**, и на него отвечает форма отдельного ряда.
 *
 * **Малые кратные — прямая рекомендация `dataviz` для шести серий.** Ряды
 * не накладываются и не касаются, поэтому цвет здесь работает как имя,
 * а не как единственный различитель: канал узнаётся по своей строке
 * и по метке, совпадающей с меткой в таблице.
 *
 * **Шкала общая для всех рядов, и это главное условие честности.** Дай
 * каждому ряду свою — Telegram с его девятнадцатью тысячами выглядел бы
 * ровно так же, как «Точка продаж» с четырьмястами шестьюдесятью восемью.
 * Ряд, прижатый к нулю, — это ответ, а не пустая строка.
 *
 * **Курсор общий на все ряды.** Наведение подсвечивает один и тот же
 * промежуток во всех строках сразу и показывает разбор недели — то самое,
 * что раньше приходилось выковыривать из стопки.
 */
export function DynamicsCard({ dynamics }: { dynamics: Dynamics }) {
  const { points, series, step } = dynamics
  if (points.length === 0 || series.length === 0) return null

  // Общая шкала: наибольшее значение по всем каналам и всем промежуткам.
  const max = Math.max(
    ...points.flatMap((point) => point.values),
    0
  )

  return (
    <Section
      title="Как менялось"
      note={`${stepNote(step)} · шкала общая для всех каналов`}
      explain={
        <Explain>
          Ряд на канал, <b>шкала у всех одна</b>: дай каждому свою, и канал
          на двадцать тысяч выглядел бы как канал на полмиллиона. <b>Шаг
          подбирается под период</b> — до месяца по дням, до полугода
          по неделям, дальше по месяцам; тот же, что на странице отгрузок.
          Показаны пять крупнейших каналов и «Другое» — свёрнутое,
          а не выброшенное. Пустой промежуток нарисован нулём: неделя
          без продаж это факт, а не отсутствие данных.
        </Explain>
      }
    >
      {/* Три колонки: имя, ряд, итог за период. Курсор — отдельный слой
          во второй колонке на всю высоту, поэтому подсветка промежутка
          проходит сразу по всем каналам. */}
      {/* Три колонки: имя, ряд, итог за период. Все ячейки размещены
          явно — курсор занимает вторую колонку на всю высоту, и без явного
          размещения автоматическая раскладка вытолкнула бы ряды из неё. */}
      <div className="grid grid-cols-[6.5rem_1fr_5.5rem] items-center gap-x-3 gap-y-1.5 max-sm:grid-cols-[5rem_1fr]">
        {/* Слой курсора идёт первым: он подсвечивает промежуток **под**
            рядами, а не поверх — заливка поверх линий скрывала бы ровно то,
            ради чего на них смотрят. События он всё равно получает: сами
            ряды объявлены неинтерактивными. */}
        <div
          className="flex h-full"
          style={{ gridColumn: 2, gridRow: `1 / ${series.length + 1}` }}
        >
          {points.map((point) => (
            <Tooltip key={point.start}>
              <TooltipTrigger
                render={
                  <div className="h-full min-w-0 flex-1 rounded-[2px] transition-colors hover:bg-accent" />
                }
              />
              <TooltipContent>
                <span className="flex flex-col gap-0.5">
                  <span className="font-medium">
                    {bucketLabel(point.start, point.end, step)}
                  </span>
                  {point.values.every((value) => value === 0) ? (
                    <span>продаж не было</span>
                  ) : (
                    point.values.map((value, place) =>
                      value > 0 ? (
                        <span key={series[place].name}>
                          {series[place].name}: {formatMoney(value)}
                        </span>
                      ) : null
                    )
                  )}
                </span>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>

        {series.map((item, place) => {
          const values = points.map((point) => point.values[place])
          const total = values.reduce((sum, value) => sum + value, 0)
          return (
            <React.Fragment key={item.name}>
              <span
                className="pointer-events-none flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground"
                style={{ gridColumn: 1, gridRow: place + 1 }}
              >
                <span
                  aria-hidden
                  className="size-2 shrink-0 rounded-[2px]"
                  style={{ background: slotColor(item.slot) }}
                />
                <span className="truncate">{item.name}</span>
              </span>
              <span
                className="pointer-events-none block"
                style={{ gridColumn: 2, gridRow: place + 1 }}
              >
                <Sparkline values={values} max={max} color={slotColor(item.slot)} />
              </span>
              <span
                className="pointer-events-none text-right text-xs tabular-nums max-sm:hidden"
                style={{ gridColumn: 3, gridRow: place + 1 }}
              >
                {formatMoney(total)}
              </span>
            </React.Fragment>
          )
        })}
      </div>

      {/* Подписан весь охват ряда — от начала первого промежутка до конца
          последнего, а не начало последнего столбика: иначе ряд выглядит
          короче, чем он есть. */}
      <div className="mt-1.5 flex justify-between text-xs text-muted-foreground tabular-nums">
        <span>{formatDay(points[0].start)}</span>
        <span>{formatDay(points[points.length - 1].end)}</span>
      </div>
    </Section>
  )
}

/**
 * Ряд одного канала: заливка под линией.
 *
 * Заливка, а не столбики: при двадцати двух промежутках в строке высотой
 * в два десятка точек столбики вырождаются в гребёнку, где не видно ни формы,
 * ни направления. Площадь читается силуэтом — ровно то, что здесь спрашивают.
 *
 * Линия поверх заливки — чтобы низкие значения не исчезали вовсе: у «Другого»
 * на общей шкале высота местами меньше пикселя, и без линии ряд выглядел бы
 * пустым, хотя продажи были.
 */
function Sparkline({
  values,
  max,
  color,
}: {
  values: number[]
  max: number
  color: string
}) {
  const width = 100
  const height = 30
  const step = values.length > 1 ? width / (values.length - 1) : width
  const y = (value: number) =>
    max > 0 ? height - (value / max) * (height - 2) - 1 : height - 1

  const line = values
    .map((value, index) => `${index === 0 ? "M" : "L"}${(index * step).toFixed(2)},${y(value).toFixed(2)}`)
    .join(" ")

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      // Координаты растягиваются по ширине, а высота фиксирована: ряд
      // сравнивают с соседним по высоте, и она обязана быть одинаковой
      // при любой ширине экрана.
      preserveAspectRatio="none"
      className="h-8 w-full"
      role="img"
    >
      <path
        d={`${line} L${width},${height} L0,${height} Z`}
        fill={color}
        fillOpacity="0.22"
      />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth="1"
        // Толщина не масштабируется вместе с координатами — иначе
        // растянутый по ширине viewBox делает линию тоньше по вертикали.
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  )
}
