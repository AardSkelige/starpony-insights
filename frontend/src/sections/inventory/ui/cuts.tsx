import { FolderTree, Warehouse } from "lucide-react"

import type { InventoryCuts } from "@/sections/inventory/api"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select"
import { cn } from "@/shared/lib/utils"

const ALL = "__all__"

/**
 * Склад и папка — два поля в ряду фильтров.
 *
 * Своими, а не общим `picker`, по двум причинам сразу: справочника здесь два,
 * а `picker` знает один, и оба значения — строки, а не идентификаторы.
 * Склада как сущности у нас нет: он приходит именем внутри инвентаризации,
 * и синтетический номер в ссылке означал бы разное в разные дни.
 *
 * Оформлены как поле «Период» и `picker` соседей: два равноправных фильтра,
 * набранные по-разному, читаются как разные по важности.
 */
export function Cuts({
  cuts,
  stores,
  folders,
  onChange,
}: {
  cuts: InventoryCuts
  stores: { id: number; name: string }[]
  folders: string[]
  onChange: (patch: Partial<InventoryCuts>) => void
}) {
  return (
    <>
      <Field
        label="Склад"
        icon={<Warehouse className="text-muted-foreground" />}
        value={cuts.store}
        options={stores.map((store) => store.name)}
        onChange={(store) => onChange({ store })}
      />
      <Field
        label="Папка"
        icon={<FolderTree className="text-muted-foreground" />}
        value={cuts.folder}
        options={folders}
        onChange={(folder) => onChange({ folder })}
      />
    </>
  )
}

function Field({
  label,
  icon,
  value,
  options,
  onChange,
}: {
  label: string
  icon: React.ReactNode
  value: string
  options: string[]
  onChange: (value: string) => void
}) {
  return (
    <Select
      value={value || ALL}
      onValueChange={(next: string | null) =>
        onChange(!next || next === ALL ? "" : next)
      }
    >
      <SelectTrigger
        aria-label={label}
        className={cn(
          "w-full justify-start gap-2 font-normal *:data-[slot=select-value]:flex-1 sm:w-44",
          // Высота задаётся тем же вариантом, что и в компоненте: `h-10`
          // проигрывает по специфичности, и поле осталось бы ниже соседних.
          "max-sm:data-[size=default]:h-10"
        )}
      >
        {icon}
        <SelectValue>{value || label}</SelectValue>
      </SelectTrigger>
      {/* Ширина по содержимому: «Готовая продукция/Кондиционер для лошадей»
          в 176 точках превращается в обрубок, по которому папку не отличить. */}
      <SelectContent
        alignItemWithTrigger={false}
        className="w-auto min-w-(--anchor-width) max-w-[min(32rem,calc(100vw-2rem))]"
      >
        <SelectGroup>
          <SelectItem value={ALL}>Все</SelectItem>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}
