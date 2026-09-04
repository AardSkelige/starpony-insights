import { Minus, Plus } from "lucide-react"

import { ICON_GROUP } from "@/app/layout/icon-group"
import { MAX_QUANTITY } from "@/sections/production/use-batch"
import { cn } from "@/shared/lib/utils"
import { Button } from "@/shared/ui/button"
import { Input } from "@/shared/ui/input"

// Столько цифр помещается в адресную строку и принимает сервер.
const DIGITS = String(MAX_QUANTITY).length

/**
 * Сколько произвести: минус, число, плюс — в одной обойме.
 *
 * **Не `type="number"`.** Встроенные стрелки браузера — две микроскопические
 * половинки в углу поля: попасть в них мышью трудно, пальцем невозможно,
 * а выглядят они одинаково во всех темах, потому что рисует их не наша
 * разметка.
 *
 * **Обойма `ICON_GROUP`** — та же, что у переключателя темы в шапке
 * и у горизонта в фильтрах: рамка одна, вокруг группы, а кнопки и поле
 * внутри своих не имеют. Три отдельные рамки в ряд читались как три
 * независимых элемента, хотя это один орган управления.
 *
 * Поле при этом остаётся полем: партию правят и на десятки, и на сотни,
 * и набрать «156» быстрее, чем нажать сто пятьдесят шесть раз.
 *
 * **Минус упирается в единицу.** Прежде он на единице снимал отметку,
 * и это выглядело поломкой: число не убавлялось, а **прыгало вверх**
 * — до подсказанного количества, которое возвращалось вместо снятого
 * значения. Убавление, увеличивающее число, объяснить нечем. Снимает
 * отметку галочка, на то она и есть.
 */
export function Quantity({
  value,
  disabled,
  label,
  onChange,
}: {
  value: number | null
  disabled?: boolean
  /** Что правим — для экранного диктора: полей на странице пятьдесят семь. */
  label: string
  onChange: (quantity: number) => void
}) {
  const current = value ?? 0

  return (
    // `onClick` гасится на всей обойме: строка — это `<label>` с галочкой,
    // и любое нажатие внутри неё иначе переключало бы отметку.
    <span
      className={cn(ICON_GROUP, "shrink-0")}
      onClick={(event) => event.preventDefault()}
    >
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={`Убавить: ${label}`}
        disabled={disabled || current <= 1}
        onClick={() => onChange(Math.max(1, current - 1))}
        className="max-sm:size-10"
      >
        <Minus />
      </Button>

      <Input
        inputMode="numeric"
        aria-label={`Сколько произвести: ${label}`}
        value={value ?? ""}
        disabled={disabled}
        onChange={(event) => {
          // Только цифры и не больше семи: буквы дали бы NaN, а NaN
          // в `setQuantity` молча снимает отметку. Семь — потолок разбора
          // адресной строки; наберись восьмая, кусок `артикул:12345678`
          // перестал бы разбираться, и позиция исчезла бы из партии
          // в момент набора.
          const digits = event.target.value.replace(/\D/g, "").slice(0, DIGITS)
          onChange(digits ? Number(digits) : 0)
        }}
        // Своей рамки нет — её даёт обойма. Подсветка при фокусе тоже
        // снимается: кольцо внутри рамки группы выглядит вторым контуром.
        className="h-7 w-9 border-0 bg-transparent px-0 text-center text-sm tabular-nums focus-visible:border-0 focus-visible:ring-0 disabled:bg-transparent max-sm:h-10 dark:bg-transparent dark:disabled:bg-transparent"
      />

      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={`Прибавить: ${label}`}
        disabled={disabled || current >= MAX_QUANTITY}
        onClick={() => onChange(Math.min(current + 1, MAX_QUANTITY))}
        className="max-sm:size-10"
      >
        <Plus />
      </Button>
    </span>
  )
}
