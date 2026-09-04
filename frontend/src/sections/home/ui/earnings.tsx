import type { Home, HomeChange, HomeChannel, HomeMargin } from "@/sections/home/api"

type HomePeriod = Home["period"]
import { withMonth } from "@/sections/home/links"
import { changesRemark, channelsRemark, marginsRemark } from "@/sections/home/remarks"
import { Tile } from "@/sections/home/ui/tile"
import { BarList } from "@/shared/components/bar-list"
import { Explain } from "@/shared/components/explain"
import { formatMoney } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * «Где зарабатываем»: маржа по товарам месяца.
 *
 * **Полосами, а не столбиком чисел.** Шесть процентов рядом с восьмьюдесятью
 * семью читаются длиной мгновенно, а списком — чтением; это правило продукта
 * (`CLAUDE.md` §8.0), а не оформления.
 *
 * **Тон появляется только там, где есть о чём предупредить.** Маржа ниже
 * трети — это позиция, которую пора пересматривать; остальные полосы одного
 * цвета, потому что товары не упорядочены и красить их значило бы второй раз
 * закодировать то, что уже показывает длина.
 */
export function MarginsTile({ margins, period }: {
  margins: HomeMargin[]
  period: HomePeriod
}) {
  const month = period.label
  if (!margins.length) return null

  return (
    <Tile
      title="Где зарабатываем"
      window={month}
      windowNote="6 % рядом с 87 % видно длиной, а не чтением"
      link={{ to: withMonth("/profitability", period, "margin"), label: "Разобрать" }}
      explain={
        <Explain>
          Маржа = (выручка − себестоимость) ÷ выручка. Оба числа — из отчёта
          прибыльности МойСклада: себестоимость там на момент продажи, по ФИФО.
          Позиции с выручкой меньше 3 000 ₽ за месяц не показаны — единичная
          продажа даёт крайнюю маржу в любую сторону и ничего не значит.
        </Explain>
      }
      remark={marginsRemark(margins) ?? undefined}
    >
      <BarList
        bars={margins.map((row) => ({
          key: row.name,
          label: row.name,
          // Длина — сама маржа в сотых долях: шкала у всех полос общая,
          // от нуля до ста процентов.
          value: row.margin,
          display: `${(row.margin / 100).toFixed(1).replace(".", ",")} %`,
          secondary: formatMoney(row.revenue_kopecks),
          hint: `${withPlural(Math.round(Number(row.quantity)), "штука", "штуки", "штук")} за месяц`,
          // Цвет здесь не про категорию, а про состояние: ниже трети —
          // цена, которую пора пересматривать. Всегда вместе с числом.
          tone: row.margin < 2000 ? "destructive" : row.margin < 4000 ? "warning" : "default",
        }))}
        wideLabels
        multilineLabels
      />
    </Tile>
  )
}

/**
 * «Что выросло и что упало»: изменение выручки против прошлого месяца.
 *
 * **Общая ось у роста и падения.** Два списка дали бы каждой половине свой
 * масштаб, и падение на 3 000 ₽ выглядело бы так же весомо, как рост
 * на 52 000 ₽. Здесь длина сравнима во всём списке.
 *
 * **Знак дублируется числом**, а не только цветом: правило `DESIGN.md` §1.
 */
export function ChangesTile({ changes, period }: {
  changes: HomeChange[]
  period: HomePeriod
}) {
  const month = period.label
  const earlierTo = period.earlier_label_to
  if (!changes.length) return null

  return (
    <Tile
      title="Что выросло и что упало"
      window={`${month} к ${earlierTo}`}
      windowNote="рублей выручки"
      link={{ to: withMonth("/profitability", period, "-revenue"), label: "Разобрать" }}
      explain={
        <Explain>
          Разница выручки по отчёту прибыльности. Товар, которого не было
          в одном из месяцев, считается наравне: пропавшая продажа — это
          падение на всю его выручку. Услуги исключены — доставку не продают.
        </Explain>
      }
      remark={changesRemark()}
    >
      <BarList
        bars={changes.map((row) => ({
          key: row.name,
          label: row.name,
          value: Math.abs(row.delta_kopecks),
          display: `${row.delta_kopecks > 0 ? "+" : "−"}${formatMoney(Math.abs(row.delta_kopecks))}`,
          hint: `${formatMoney(row.earlier_kopecks)} → ${formatMoney(row.now_kopecks)}`,
          tone: row.delta_kopecks < 0 ? "destructive" : "default",
        }))}
        wideLabels
        multilineLabels
      />
    </Tile>
  )
}

/**
 * «Кто дал деньги»: выручка отгрузок по каналам.
 *
 * Источник здесь — документы, а не отчёт прибыльности, и это сказано
 * в подписи. Смешай их — суммы каналов сложились бы в отгруженное, а рядом
 * с маржой читались бы как проданное.
 */
export function ChannelsTile({ channels, period }: {
  channels: HomeChannel[]
  period: HomePeriod
}) {
  const month = period.label
  if (!channels.length) return null

  return (
    <Tile
      title="Кто дал деньги"
      window={month}
      windowNote="по отгрузкам, а не по отчёту прибыльности"
      link={{ to: withMonth("/channels", period), label: "Разобрать" }}
      remark={channelsRemark()}
    >
      <BarList
        bars={channels.map((row) => ({
          key: row.name,
          label: row.name,
          value: row.revenue_kopecks,
          display: formatMoney(row.revenue_kopecks),
          hint: withPlural(row.documents, "отгрузка", "отгрузки", "отгрузок"),
        }))}
      />
    </Tile>
  )
}
