import { ru } from "date-fns/locale"
import { CalendarDays, ChevronDown, Radio, Search, X } from "lucide-react"
import type { DateRange } from "react-day-picker"

import type { ShipmentProducts } from "@/sections/shipments-products/api"
import { cn } from "@/shared/lib/utils"
import { Button } from "@/shared/ui/button"
import { Calendar } from "@/shared/ui/calendar"
import { Input } from "@/shared/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select"

export type FilterValue = {
  dateFrom: string | null
  dateTo: string | null
  channelId: number | null
  search: string
}

type Props = {
  value: FilterValue
  onChange: (patch: Partial<FilterValue>) => void
  onReset: () => void
  channels: ShipmentProducts["channels"]
  /** В выдвижной панели поля идут в столбец и занимают всю ширину. */
  stacked?: boolean
}

const ALL_CHANNELS = "all"

export function Filters({ value, onChange, onReset, channels, stacked = false }: Props) {
  const dirty =
    Boolean(value.dateFrom || value.dateTo || value.channelId) || value.search !== ""

  return (
    <>
      <div className={stacked ? "w-full" : "relative w-full sm:w-56"}>
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          value={value.search}
          onChange={(event) => onChange({ search: event.target.value })}
          placeholder="Название, артикул или код"
          aria-label="Поиск по товарам"
          className="pl-8"
        />
      </div>

      <PeriodField value={value} onChange={onChange} stacked={stacked} />

      <Select
        value={value.channelId ? String(value.channelId) : ALL_CHANNELS}
        onValueChange={(next: string | null) =>
          onChange({ channelId: !next || next === ALL_CHANNELS ? null : Number(next) })
        }
      >
        <SelectTrigger
          aria-label="Канал продаж"
          className={cn(
            "justify-start gap-2 font-normal *:data-[slot=select-value]:flex-1",
            stacked ? "w-full" : "w-44"
          )}
        >
          {/* Подпись собирается сама: `SelectValue` без детей показывает
              значение — то есть «all» или числовой идентификатор канала. */}
          {/* Иконка слева — чтобы поле выглядело так же, как соседний
              «Период»: два равноправных фильтра, набранные по-разному,
              читаются как разные по важности. */}
          <Radio className="text-muted-foreground" />
          <SelectValue>
            {value.channelId
              ? (channels.find((channel) => channel.id === value.channelId)?.name ??
                "Канал")
              : "Канал"}
          </SelectValue>
        </SelectTrigger>
        {/* Список раскрывается под полем, а не поверх него. По умолчанию
            `Select` из реестра совмещает выбранный пункт с триггером — как
            нативный select в macOS: список наезжает на поле, обрезается
            сверху и дёргается при открытии. */}
        <SelectContent alignItemWithTrigger={false}>
          <SelectGroup>
            {/* В раскрытом списке слово «Канал» лишнее: заголовок уже
                сказал, из чего выбирают. */}
            <SelectItem value={ALL_CHANNELS}>Все</SelectItem>
            {channels.map((channel) => (
              <SelectItem key={channel.id} value={String(channel.id)}>
                {channel.name}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>

      {dirty ? (
        <Button
          variant="ghost"
          size={stacked ? "default" : "sm"}
          onClick={onReset}
          className={stacked ? "w-full" : undefined}
        >
          <X data-icon="inline-start" />
          Сбросить
        </Button>
      ) : null}
    </>
  )
}

function PeriodField({
  value,
  onChange,
  stacked,
}: {
  value: FilterValue
  onChange: (patch: Partial<FilterValue>) => void
  stacked: boolean
}) {
  const range: DateRange | undefined = value.dateFrom
    ? { from: parseDay(value.dateFrom), to: value.dateTo ? parseDay(value.dateTo) : undefined }
    : undefined

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            variant="outline"
            aria-label="Период"
            className={cn(
              "justify-start gap-2 font-normal",
              stacked ? "w-full" : "w-44"
            )}
          >
            <CalendarDays data-icon="inline-start" className="text-muted-foreground" />
            <span className="flex-1 text-left">{label(value)}</span>
            <ChevronDown className="text-muted-foreground" />
          </Button>
        }
      />
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="range"
          locale={ru}
          selected={range}
          defaultMonth={range?.from}
          numberOfMonths={stacked ? 1 : 2}
          onSelect={(next: DateRange | undefined) =>
            onChange({
              dateFrom: next?.from ? toDay(next.from) : null,
              dateTo: next?.to ? toDay(next.to) : null,
            })
          }
        />
      </PopoverContent>
    </Popover>
  )
}

function label(value: FilterValue): string {
  if (!value.dateFrom && !value.dateTo) return "Период"
  const from = value.dateFrom ? short(value.dateFrom) : "…"
  const to = value.dateTo ? short(value.dateTo) : "…"
  return `${from} — ${to}`
}

/**
 * Дата без времени и без пояса.
 *
 * `new Date("2026-04-01")` разбирается как полночь UTC и в Москве становится
 * третьим часом того же дня, а при сдвиге на запад — предыдущим днём.
 * Поэтому день собирается по частям, а не через разбор строки.
 */
function parseDay(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number)
  return new Date(year, month - 1, day)
}

function toDay(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${date.getFullYear()}-${month}-${day}`
}

function short(iso: string): string {
  const date = parseDay(iso)
  return `${String(date.getDate()).padStart(2, "0")}.${String(date.getMonth() + 1).padStart(2, "0")}`
}
