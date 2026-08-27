import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select"
import { PAGE_SIZES } from "@/shared/components/data-table/columns"

/** Сколько строк показывать на странице. Значения — в описании таблицы. */
export function PageSize({
  value,
  onChange,
}: {
  value: number
  onChange: (size: number) => void
}) {
  return (
    <Select
      value={String(value)}
      onValueChange={(next: string | null) => next && onChange(Number(next))}
    >
      <SelectTrigger size="sm" aria-label="Строк на странице" className="w-auto">
        <SelectValue>{`${value} строк`}</SelectValue>
      </SelectTrigger>
      {/* Под полем, а не поверх него — см. фильтр каналов. */}
      <SelectContent alignItemWithTrigger={false}>
        <SelectGroup>
          {PAGE_SIZES.map((size) => (
            <SelectItem key={size} value={String(size)}>
              {size}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}
