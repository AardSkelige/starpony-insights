import type { Profitability } from "@/sections/profitability/api"
import { BarList, type Bar } from "@/shared/components/bar-list"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { formatMoney, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * «По линейкам»: сколько приносит группа продукции и с какой маржой.
 *
 * **Два списка, а не один.** Линейка может приносить больше всех и при этом
 * иметь не лучшую маржу: Репеллент второй по деньгам и последний по марже.
 * Один список отвечал бы на два вопроса сразу и на оба неверно — колонка
 * чисел рядом с полосой читается как второе измерение той же шкалы.
 *
 * Линейка — последнее звено пути группы в номенклатуре: «Готовая
 * продукция/Репеллент» это «Репеллент». Полный путь дал бы семь подписей,
 * различающихся концом, а первое звено — одну «Готовую продукцию» на всех.
 */
export function Families({
  families,
}: {
  families: Profitability["families"]
}) {
  if (families.length === 0) return null

  // `?? 0` в сравнении ставил линейку без маржи выше любой убыточной,
  // и заголовок читался «лучшая «X», —». Неизвестное в выбор не участвует.
  const ranked = families.filter((family) => family.margin !== null)
  const best = [...ranked].sort((a, b) => Number(b.margin) - Number(a.margin))[0]

  return (
    <CollapsibleNote
      title="По линейкам"
      headline={
        best ? `лучшая «${best.name}», ${formatShare(best.margin)}` : undefined
      }
    >
      <div className="flex flex-col gap-6">
        <section className="flex flex-col gap-3">
          <h3 className="text-xs text-muted-foreground">Сколько приносит линейка</h3>
          <BarList bars={byProfit(families)} wideLabels />
        </section>
        <section className="flex flex-col gap-3">
          <h3 className="text-xs text-muted-foreground">С какой маржой</h3>
          <BarList bars={byMargin(families)} wideLabels />
        </section>
      </div>
    </CollapsibleNote>
  )
}

function byProfit(families: Profitability["families"]): Bar[] {
  return [...families]
    .sort((a, b) => b.profit_kopecks - a.profit_kopecks)
    .map((family) => ({
      key: family.name,
      label: family.name,
      value: Math.max(family.profit_kopecks, 0),
      display: formatMoney(family.profit_kopecks),
      // Число товаров и маржа — в подсказке: колонка вторых чисел узкая,
      // и «36 товаров» переносится на вторую строку, ломая высоту ряда.
      hint: `${withPlural(family.products_count, "товар", "товара", "товаров")} · выручка ${formatMoney(family.revenue_kopecks)}, маржа ${formatShare(family.margin)}`,
    }))
}

function byMargin(families: Profitability["families"]): Bar[] {
  return [...families]
    .sort((a, b) => Number(b.margin ?? 0) - Number(a.margin ?? 0))
    .map((family) => ({
      key: family.name,
      label: family.name,
      // Длина — маржа в процентах, шкала общая для всех линеек.
      // Отрицательная маржа отдаётся модулем и красным: длина у полосы
      // не бывает отрицательной, а знак несут цвет и само число.
      value: Math.abs(Number(family.margin ?? 0)) * 100,
      tone: Number(family.margin ?? 0) < 0 ? ("destructive" as const) : undefined,
      display: formatShare(family.margin),
      hint: `Прибыль ${formatMoney(family.profit_kopecks)} из выручки ${formatMoney(family.revenue_kopecks)}`,
    }))
}
