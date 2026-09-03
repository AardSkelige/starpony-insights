import type * as React from "react"
import { ru } from "date-fns/locale"
import { CalendarDays, ChevronDown, Search, X } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import type { DateRange } from "react-day-picker"

import type { FilterOption } from "@/shared/api/types"
import { formatDate, formatDayMonth } from "@/shared/lib/format"
import { useScreen, type Screen } from "@/shared/hooks/use-screen"
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

/**
 * Фильтры выборки: период, справочник, поиск.
 *
 * Живут в `shared/`, потому что понадобились второй странице — правило
 * переезда из `CLAUDE.md`. Отличается у страниц два места: что ищут
 * (у «Товаров» строка таблицы — проданный товар, у «Материалов» — сырьё)
 * и **чем сужают выборку**.
 *
 * **Справочник настраивается страницей, а не зашит.** Сначала здесь был
 * «Канал продаж». У приёмки канала не существует — товар приходит
 * от контрагента, а не через Озон, — и вместо второго почти такого же
 * компонента страница передаёт подпись, иконку и список: `?channel=7`
 * у отгрузок, `?supplier=7` у приёмок.
 *
 * **А ещё его может не быть вовсе.** У «Поставщиков» поставщик — это строка
 * таблицы: выбери его фильтром, и в ней останется одна строка, а переключиться
 * будет нечем, кроме сброса. Там фильтров два: период и поиск.
 *
 * **Периода тоже может не быть.** У «Сроков оплаты» долг — это состояние
 * на сегодня, а не итог за отрезок: выбери человек «август», и долг возрастом
 * 93 дня исчез бы с экрана — фильтр спрятал бы ровно то, ради чего страницу
 * открывают. Там фильтр один: поиск.
 *
 * **На телефоне поля стоят в столбик прямо на странице, а не в выдвижной
 * панели.** Панель была ошибкой: чтобы найти позицию, приходилось нажать
 * «Фильтры», дождаться анимации, ввести запрос и закрыть панель — четыре
 * действия там, где ожидается одно. Три поля во всю ширину занимают
 * на 48 точек больше, и это честная плата.
 */
export type FilterValue = {
  dateFrom: string | null
  dateTo: string | null
  /** Что выбрано в справочнике страницы: канал или поставщик. */
  pickId: number | null
  search: string
}

/** Чем эта страница сужает выборку. */
export type Picker = {
  /**
   * Имя в адресной строке; в запрос уходит как `<key>_id`.
   *
   * Своё у каждой страницы намеренно: ссылка «канал 3», открытая
   * на приёмках, иначе выбрала бы поставщика с идентификатором 3.
   */
  key: string
  /** Подпись поля и то, что читает экранный диктор: «Канал», «Поставщик». */
  label: string
  icon: LucideIcon
  options: FilterOption[]
}

type Props = {
  value: FilterValue
  onChange: (patch: Partial<FilterValue>) => void
  onReset: () => void
  picker?: Picker
  /**
   * Сужается ли выборка периодом.
   *
   * `false` у «Сроков оплаты»: там показано состояние на сегодня, и период
   * не сужал бы выборку, а прятал часть долга. Поле не просто скрывается —
   * его значение перестаёт считаться применённым фильтром, иначе кнопка
   * «Сбросить» появлялась бы из-за дат, которых на экране нет.
   */
  period?: boolean
  /** Что ищут на этой странице — подсказка в поле и подпись для чтения с экрана. */
  searchPlaceholder: string
  searchLabel: string
  /**
   * Свои переключатели страницы — встают в тот же ряд, перед «Сбросить».
   *
   * Заведён для «Прибыльности»: там выборку сужает не только период
   * и поиск, но и **база расчёта** («Продано» против «Отгружено») с признаком
   * «без подарков». Оба меняют показанные числа так же, как период, — значит
   * их место рядом с ним, а не отдельной строкой над таблицей: два ряда
   * управления читаются как два разных по важности набора.
   *
   * Слотом, а не полем в `FilterValue`: у остальных девяти страниц такого
   * выбора нет, и общий тип обзавёлся бы полями, которые никто не заполняет.
   * Сброс их не трогает — «Сбросить» убирает **сужение выборки**, а база
   * расчёта не сужает её, а меняет вопрос.
   */
  extra?: React.ReactNode
}

const ALL = "all"

// Высота поля на телефоне. 40 точек — минимум, под который попадает палец
// (DESIGN §15); на большом экране поля ниже, там мышь.
const PHONE_HEIGHT = "max-sm:h-10"

export function Filters({
  value,
  onChange,
  onReset,
  picker,
  period = true,
  searchPlaceholder,
  searchLabel,
  extra,
}: Props) {
  const dirty =
    Boolean((period && (value.dateFrom || value.dateTo)) || value.pickId) ||
    value.search !== ""

  return (
    <>
      <div className="relative w-full sm:w-56">
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          value={value.search}
          onChange={(event) => onChange({ search: event.target.value })}
          placeholder={searchPlaceholder}
          aria-label={searchLabel}
          className={cn("pl-8", PHONE_HEIGHT)}
        />
      </div>

      {period ? <PeriodField value={value} onChange={onChange} /> : null}

      {picker ? <PickerField value={value} onChange={onChange} picker={picker} /> : null}

      {extra}

      {dirty ? (
        <Button
          variant="outline"
          size="sm"
          onClick={onReset}
          className={cn("max-sm:w-full", PHONE_HEIGHT)}
        >
          <X data-icon="inline-start" />
          Сбросить
        </Button>
      ) : null}
    </>
  )
}

/**
 * Справочник страницы отдельным компонентом.
 *
 * Вынесен, потому что его может не быть: условие вокруг тридцати строк
 * разметки читается хуже, чем условие вокруг одного вызова, — а забыть
 * закрыть его посреди `Select` куда легче.
 */
function PickerField({
  value,
  onChange,
  picker,
}: {
  value: FilterValue
  onChange: (patch: Partial<FilterValue>) => void
  picker: Picker
}) {
  const PickIcon = picker.icon

  return (
      <Select
        value={value.pickId ? String(value.pickId) : ALL}
        onValueChange={(next: string | null) =>
          onChange({ pickId: !next || next === ALL ? null : Number(next) })
        }
      >
        <SelectTrigger
          aria-label={picker.label}
          className={cn(
            "w-full justify-start gap-2 font-normal *:data-[slot=select-value]:flex-1 sm:w-44",
            // Высота задаётся тем же вариантом, что и в компоненте, —
            // иначе `h-10` проигрывает по специфичности и поле остаётся
            // ниже соседних.
            "max-sm:data-[size=default]:h-10"
          )}
        >
          {/* Иконка слева — чтобы поле выглядело так же, как соседний
              «Период»: два равноправных фильтра, набранные по-разному,
              читаются как разные по важности. */}
          <PickIcon className="text-muted-foreground" />
          <SelectValue>
            {value.pickId
              ? (picker.options.find((option) => option.id === value.pickId)?.name ??
                picker.label)
              : picker.label}
          </SelectValue>
        </SelectTrigger>
        {/* Список раскрывается под полем, а не поверх него. По умолчанию
            `Select` из реестра совмещает выбранный пункт с триггером — как
            нативный select в macOS: список наезжает на поле, обрезается
            сверху и дёргается при открытии. */}
        <SelectContent alignItemWithTrigger={false}>
          <SelectGroup>
            {/* В раскрытом списке подпись поля лишняя: заголовок уже
                сказал, из чего выбирают. */}
            <SelectItem value={ALL}>Все</SelectItem>
            {picker.options.map((option) => (
              <SelectItem key={option.id} value={String(option.id)}>
                {option.name}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
  )
}

function PeriodField({
  value,
  onChange,
}: {
  value: FilterValue
  onChange: (patch: Partial<FilterValue>) => void
}) {
  // Календарь на телефоне помещается только в один месяц — это про
  // содержимое, а не про оформление, и классами не задаётся.
  const screen = useScreen()

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
            className={cn("w-full justify-start gap-2 font-normal sm:w-44", PHONE_HEIGHT)}
          >
            <CalendarDays data-icon="inline-start" className="text-muted-foreground" />
            <span className="flex-1 truncate text-left">{label(value, screen)}</span>
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
          numberOfMonths={screen === "phone" ? 1 : 2}
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

/**
 * Подпись периода. На телефоне — с годом, на большом экране — без него.
 *
 * Это не описка: на телефоне поле занимает всю ширину, год помещается
 * и снимает вопрос «апрель какого года». В ряду фильтров на большом экране
 * поле узкое, а год виден в календаре по нажатию.
 */
function label(value: FilterValue, screen: Screen): string {
  if (!value.dateFrom && !value.dateTo) return "Период"

  const format = screen === "phone" ? formatDate : formatDayMonth
  const from = value.dateFrom ? format(value.dateFrom) : "…"
  const to = value.dateTo ? format(value.dateTo) : "…"
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
