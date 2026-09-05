import type { InventoryWorst } from "@/sections/inventory/api"
import { BarList, type Bar } from "@/shared/components/bar-list"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { Explain } from "@/shared/components/explain"
import { SummaryStat } from "@/shared/components/summary-stat"
import { formatMoney, formatQuantity } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * «Где не сходится» — расхождения, которые дороже всего обходятся.
 *
 * По последнему пересчёту каждой позиции, ровно как таблица. Сложи блок всю
 * историю, два числа на одном экране означали бы разное, оставаясь оба
 * верными, — дефект, который на «Каналах» стоил 281 126 ₽ непонимания.
 *
 * Полосы одного тона: знак несёт само число у конца полосы, а длина —
 * размер. Красить недостачу в красный значило бы закодировать цветом то,
 * что уже написано минусом.
 */
export function Worst({ worst }: { worst: InventoryWorst }) {
  const bars: Bar[] = worst.items.map((item) => ({
    key: `${item.product_id}`,
    label: item.name,
    value: Math.abs(item.money_kopecks),
    display: formatMoney(item.money_kopecks),
    secondary: `${Number(item.correction) > 0 ? "+" : ""}${formatQuantity(item.correction, item.uom)}`,
  }))

  return (
    <CollapsibleNote title="Где не сходится" headline={headline(worst)}>
      <div className="mb-4 grid gap-x-6 gap-y-3 sm:grid-cols-3">
        <SummaryStat
          label="Расхождение в деньгах"
          value={formatMoney(worst.money_kopecks)}
          note="по последнему пересчёту каждой позиции"
          explain={
            <Explain>
              <b>Сумма «расхождение × себестоимость» по всем позициям
              выборки.</b> Считаем сами: в документах инвентаризации цена
              заполнена у меньшинства строк, и учёт показывает по остальным
              0 ₽ при живой недостаче. Себестоимость берётся сегодняшняя,
              поэтому с карточкой документа число не сойдётся.
            </Explain>
          }
        />
        <SummaryStat
          label="Разошлось позиций"
          value={`${worst.diverged_count} из ${worst.counted_count}`}
          note="среди пересчитанных"
          explain={
            <Explain>
              Знаменатель — <b>пересчитанные</b>, а не вся номенклатура:
              разойтись может только то, что считали. Позиции, до которых
              не дошли, — в соседнем блоке.
            </Explain>
          }
        />
        <SummaryStat
          label="Не оценено"
          value={`${worst.unpriced_count}`}
          note="расхождений без себестоимости"
          quiet
          explain={
            <Explain>
              Позиции, где расхождение есть, а умножать его не на что:
              себестоимости в остатках нет. В сумму слева они{" "}
              <b>не входят</b> — поэтому она занижена, и это видно здесь,
              а не выясняется потом.
            </Explain>
          }
        />
      </div>

      {bars.length > 0 ? (
        <BarList bars={bars} wideLabels multilineLabels />
      ) : (
        <p className="text-xs text-muted-foreground">
          Расхождений с денежной оценкой в этой выборке нет.
        </p>
      )}
    </CollapsibleNote>
  )
}

function headline(worst: InventoryWorst): string {
  if (worst.diverged_count === 0) return "в этой выборке всё сошлось"
  return `${formatMoney(worst.money_kopecks)} · ${withPlural(worst.diverged_count, "позиция", "позиции", "позиций")} из ${worst.counted_count}`
}
