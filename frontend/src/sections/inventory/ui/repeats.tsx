import type { InventoryRepeats } from "@/sections/inventory/api"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { withPlural } from "@/shared/lib/plural"

/**
 * «Расходится из раза в раз» — единственный блок страницы про всю историю.
 *
 * Смотрит на все пересчёты намеренно: позиция, разошедшаяся дважды из двух, —
 * это не случайность счёта, а место, где учёт систематически расходится
 * с полкой. Такое чинят не пересчётом, а разбором: как этот товар списывают.
 *
 * Списком, а не полосами: сравнивать здесь нечего — у всех строк «2 из 2»,
 * и полоса рисовала бы одинаковую длину десять раз подряд.
 */
export function Repeats({ repeats }: { repeats: InventoryRepeats }) {
  if (repeats.count === 0) return null

  return (
    <CollapsibleNote
      title="Расходится из раза в раз"
      headline={`${withPlural(repeats.count, "позиция", "позиции", "позиций")} — расхождение не первое`}
    >
      <ul className="flex flex-col gap-2">
        {repeats.items.map((item) => (
          <li
            key={item.product_id}
            className="flex items-baseline justify-between gap-3 text-sm"
          >
            <span className="flex min-w-0 flex-col">
              <span className="whitespace-normal">{item.name}</span>
              <span className="text-xs text-muted-foreground">
                {item.folder || "Без папки"}
              </span>
            </span>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {item.diverged_times} из {item.counted_times}
            </span>
          </li>
        ))}
      </ul>
    </CollapsibleNote>
  )
}
