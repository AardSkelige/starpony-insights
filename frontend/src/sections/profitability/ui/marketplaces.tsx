import type { Profitability } from "@/sections/profitability/api"
import { Split } from "@/sections/profitability/ui/split"
import { BarList, type Bar } from "@/shared/components/bar-list"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { formatMoney, formatShare } from "@/shared/lib/format"

/**
 * «Через площадки и напрямую»: две маржи, из которых верна одна.
 *
 * Полосы, а не два числа: вопрос к блоку — «насколько одно больше другого»,
 * и на него отвечает длина. Площадки окрашены `warning` **и подписаны**:
 * цвет здесь кодирует не категорию, а надёжность числа, и цветом
 * в одиночку такое не говорят.
 *
 * Разбивки по конкретным площадкам с сервера не приходит — она стоила бы
 * девяти лишних запросов к МойСкладу в каждую ночь ради одного блока.
 * Поэтому здесь две полосы, а не четыре: «через площадки» целиком против
 * «напрямую». Кто именно внутри — видно по значку в строках таблицы.
 */
export function Marketplaces({
  marketplaces,
}: {
  marketplaces: Profitability["marketplaces"]
}) {
  if (marketplaces.marketplace_revenue_kopecks <= 0) return null

  const bars: Bar[] = [
    {
      key: "marketplace",
      label: "Через площадки",
      // Длина — маржа в процентах: полосы сравниваются между собой,
      // а не с выручкой, и шкала у них общая.
      value: Math.abs(Number(marketplaces.marketplace_margin ?? 0)) * 100,
      display: formatShare(marketplaces.marketplace_margin),
      // Деньги — в подсказке и в полосе состава ниже: колонка вторых чисел
      // узкая, и сумма в ней переносится. Вопрос к полосам один — какая
      // маржа больше, — и на него отвечает длина.
      hint: `${formatMoney(marketplaces.marketplace_revenue_kopecks)} выручки · комиссия площадки не вычтена, её нет в учёте`,
      tone: "warning",
    },
    {
      key: "direct",
      label: "Напрямую",
      value: Math.abs(Number(marketplaces.direct_margin ?? 0)) * 100,
      display: formatShare(marketplaces.direct_margin),
      hint: `${formatMoney(marketplaces.direct_revenue_kopecks)} выручки · здесь вычитать нечего, маржа настоящая`,
    },
  ]

  return (
    <CollapsibleNote
      title="Через площадки и напрямую"
      headline={`${formatShare(marketplaces.marketplace_margin)} против ${formatShare(marketplaces.direct_margin)}`}
    >
      <div className="flex flex-col gap-5">
        <BarList bars={bars} wideLabels />
        <Split
          left={{
            label: `Площадки · ${formatMoney(marketplaces.marketplace_revenue_kopecks)}`,
            value: marketplaces.marketplace_revenue_kopecks,
            tone: "warning",
          }}
          right={{
            label: `Напрямую · ${formatMoney(marketplaces.direct_revenue_kopecks)}`,
            value: Math.max(marketplaces.direct_revenue_kopecks, 0),
          }}
          caption="Столько выручки приходит через площадку — и по нему маржа завышена ровно на её процент"
        />
      </div>
    </CollapsibleNote>
  )
}
