import type { InventoryDocuments } from "@/sections/inventory/api"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { Explain } from "@/shared/components/explain"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/ui/collapsible"
import { ChevronDown } from "lucide-react"
import { formatDate, formatMoney, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * «Склады» — когда каждый считали, сколько его пересчитано и на сколько
 * денег не проверено.
 *
 * Строка — склад, а не документ: пересчёт всегда про один склад целиком,
 * и список бумаг сам по себе — то, что человек и так видит в учёте
 * (`CLAUDE.md` §8.0). Документы живут внутри своего склада, по раскрытию:
 * они отвечают на второй вопрос — «что тогда нашли», — а не на первый.
 *
 * Доля считается от того, что на складе **лежит** сейчас. От всей
 * номенклатуры она объявила бы «Готовую продукцию» заброшенной за то,
 * что на ней нет сырья.
 */
export function Documents({ documents }: { documents: InventoryDocuments }) {
  if (documents.count === 0 && documents.stores.length === 0) return null

  return (
    <CollapsibleNote title="Склады" headline={headline(documents)}>
      <div className="flex flex-col gap-2">
        {documents.stores.map((store) => {
          const papers = documents.items.filter(
            (item) => item.store_name === store.store_name
          )
          return (
            <Collapsible key={store.store_name}>
              <CollapsibleTrigger
                render={
                  <button
                    type="button"
                    className="group flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  />
                }
              >
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                    <span className="text-sm font-medium">{store.store_name}</span>
                    <span className="text-xs text-muted-foreground">
                      {store.moment
                        ? `${formatDate(store.moment)} · ${withPlural(store.days_ago ?? 0, "день", "дня", "дней")} назад`
                        : "не считали ни разу"}
                    </span>
                  </span>
                  <span className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                    <span>
                      пересчитано{" "}
                      <b className="font-medium text-foreground">
                        {store.counted_count} из {store.products_count}
                      </b>{" "}
                      · {formatShare(store.share)}
                    </span>
                    {/* Деньги превращают долю из отметки в задачу: «18 %»
                        само по себе не говорит, стоит ли идти считать. */}
                    <span>
                      не проверено{" "}
                      <b className="font-medium text-foreground">
                        {formatMoney(store.unchecked_kopecks)}
                      </b>
                    </span>
                  </span>
                </span>
                <ChevronDown
                  aria-hidden
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-data-[panel-open]:rotate-180"
                />
              </CollapsibleTrigger>
              <CollapsibleContent>
                <ul className="flex flex-col gap-3 px-3 pt-3 pb-1">
                  {papers.map((item) => (
                    <li key={item.inventory_id} className="flex flex-col gap-0.5 text-sm">
                      <span className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                        <span className="font-medium">{formatDate(item.moment)}</span>
                        <span className="text-muted-foreground">№ {item.number}</span>
                        <span className="tabular-nums text-muted-foreground">
                          разошлось {item.diverged_count} из {item.positions_count}
                        </span>
                      </span>
                      {/* Комментарий — то, чего числом не сказать: в нём
                          написано, зачем считали и что нашли. */}
                      {item.description ? (
                        <span className="whitespace-normal text-xs text-muted-foreground">
                          {item.description}
                        </span>
                      ) : null}
                    </li>
                  ))}
                  {papers.length === 0 ? (
                    <li className="text-xs text-muted-foreground">
                      Инвентаризаций по этому складу в учёте нет.
                    </li>
                  ) : null}
                </ul>
              </CollapsibleContent>
            </Collapsible>
          )
        })}
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Доля считается от позиций, которые на складе лежат сейчас, а не от всей
        номенклатуры{" "}
        <Explain>
          <b>Знаменатель — ненулевые остатки этого склада.</b> Считай мы
          от всей номенклатуры, «Готовая продукция» выглядела бы заброшенной
          просто потому, что сырьё лежит не на ней. Числитель — позиции,
          попадавшие в инвентаризацию <b>этого</b> склада: пересчёт
          на соседнем про этот ничего не говорит.
        </Explain>
      </p>
    </CollapsibleNote>
  )
}

function headline(documents: InventoryDocuments): string {
  const worst = documents.stores[0]
  if (!worst) return `${withPlural(documents.count, "инвентаризация", "инвентаризации", "инвентаризаций")}`
  return `${withPlural(documents.stores.length, "склад", "склада", "складов")} · не проверено ${formatMoney(worst.unchecked_kopecks)} на складе «${worst.store_name}»`
}
