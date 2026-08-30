import type { CSSProperties } from "react"

import type { useProductDetail } from "@/sections/shipments-products/api"
import { Failed, Loading, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatMoney, formatQuantity } from "@/shared/lib/format"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

/**
 * Продажи во времени — столбики по дням, неделям или месяцам.
 *
 * **Заменило журнал последних отгрузок.** Тот отвечал на «кому и когда»
 * списком из десяти строк — при том что у ходового товара отгрузок 109,
 * и по строке «00278 · Ложис Софья · 1 шт · 0 ₽» решение не принимают.
 * Вопрос, на который до сих пор не отвечало ничто на странице, —
 * **растёт или падает**, и на него отвечает форма ряда, а не список.
 *
 * **Все столбики одного тона.** Промежутки времени упорядочены, но не
 * образуют категорий: покрасить каждый своим цветом значило бы второй раз
 * закодировать то, что уже показывает положение по оси.
 *
 * **Пустые промежутки нарисованы нулём, а не пропущены.** Неделя без продаж
 * — это факт: выбрось её, и провал в спросе превратится в непрерывный ряд,
 * где ничего не случилось.
 */
type Detail = ReturnType<typeof useProductDetail>

export function TimelineSection({
  detail,
  uom,
  bare = false,
}: {
  detail: Detail
  uom: string
  bare?: boolean
}) {
  if (detail.isError) {
    return (
      <Section title="Когда продавали" bare={bare}>
        <Failed onRetry={() => detail.refetch()} />
      </Section>
    )
  }

  if (detail.isPending || !detail.data) {
    return (
      <Section title="Когда продавали" bare={bare}>
        <Loading count={3} />
      </Section>
    )
  }

  const { step, step_label: stepLabel, points } = detail.data.timeline
  if (points.length === 0) return null

  const max = Math.max(...points.map((point) => Number(point.quantity)), 0)
  const total = points.reduce((sum, point) => sum + Number(point.quantity), 0)

  return (
    <Section
      title="Когда продавали"
      bare={bare}
      note={`${formatQuantity(String(total), uom)} · ${stepLabel}`}
      explain={
        <Explain>
          Сколько штук уходило за каждый промежуток. <b>Шаг подбирается под
          период</b>: до месяца — по дням, до полугода — по неделям, дальше —
          по месяцам. Пустые промежутки нарисованы нулём: неделя без продаж
          это факт, а не отсутствие данных.
        </Explain>
      }
    >
      {/* Дорожки у столбиков нет намеренно: их сравнивают друг с другом
          и с нулевой линией, а не с долей от целого — в отличие от полос
          по каналам, где вопрос «какая часть». */}
      <div className="flex h-20 items-end gap-px" role="img" aria-label={`Продажи ${stepLabel}`}>
        {points.map((point, index) => {
          const value = Number(point.quantity)
          const order = points.length > 1 ? index / (points.length - 1) : 0
          return (
            <Tooltip key={point.start}>
              <TooltipTrigger
                render={
                  <div className="flex h-full min-w-0 flex-1 items-end">
                    {/* Полоса в пиксель у пустого промежутка: столбик нулевой
                        высоты неотличим от промежутка, которого нет вовсе. */}
                    <span
                      className="motion-timeline-reveal w-full rounded-t-[3px] bg-primary"
                      style={
                        {
                          height:
                            max > 0
                              ? `${Math.max((value / max) * 100, 1.5)}%`
                              : "1.5%",
                          opacity: value > 0 ? 1 : 0.18,
                          // Доля, а не миллисекунды: семь и шестьдесят
                          // столбиков укладываются в одну общую длительность.
                          "--motion-order": order,
                        } as CSSProperties
                      }
                    />
                  </div>
                }
              />
              <TooltipContent>
                {bucketLabel(point.start, point.end, step)}:{" "}
                {formatQuantity(point.quantity, uom)} на{" "}
                {formatMoney(point.revenue_kopecks)}
              </TooltipContent>
            </Tooltip>
          )
        })}
      </div>

      {/* Подписаны только концы ряда, и подписан **весь охват** — от начала
          первого промежутка до конца последнего. Раньше справа стояло начало
          последнего столбика, и ряд выглядел короче, чем он есть. */}
      <div className="mt-1.5 flex justify-between text-xs text-muted-foreground tabular-nums">
        <span>{formatDay(points[0].start)}</span>
        <span>{formatDay(points[points.length - 1].end)}</span>
      </div>
    </Section>
  )
}

const MONTHS = [
  "январь", "февраль", "март", "апрель", "май", "июнь",
  "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]

/** Дата коротко: «29.06.26». */
function formatDay(iso: string): string {
  const [year, month, day] = iso.split("-")
  return `${day}.${month}.${year.slice(2)}`
}

/**
 * Как назвать один столбик.
 *
 * **Промежуток, а не его начало.** «29.06.26: 6 шт» под подписью «по неделям»
 * читалось как продажа двадцать девятого июня — вопрос «это дни видимо?»
 * возник на первом же показе. Неделя называет обе границы, месяц — своё имя,
 * и только день остаётся одной датой, потому что он ею и является.
 */
function bucketLabel(start: string, end: string, step: string): string {
  if (step === "day") return formatDay(start)
  if (step === "month") {
    const [year, month] = start.split("-")
    return `${MONTHS[Number(month) - 1]} ${year}`
  }
  return `${formatDay(start)} – ${formatDay(end)}`
}
