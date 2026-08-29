import { Minus, TrendingDown, TrendingUp } from "lucide-react"

import { cn } from "@/shared/lib/utils"
import { formatQuantity, formatShare, formatUnitPrice } from "@/shared/lib/format"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

/**
 * Изменение цены к предыдущей закупке.
 *
 * **Цвет не единственный признак.** Рядом с процентом стоит стрелка,
 * и знак читается без цвета — при дальтонизме, в печати и в режиме
 * высокой контрастности. Правило статусных цветов из скила `dataviz`
 * и §1 `DESIGN.md`.
 *
 * **Подорожало — красным, подешевело — зелёным.** Это про деньги компании,
 * а не про рост показателя: закупочная цена вверх — плохая новость.
 *
 * **Наведение показывает обе цены и обе партии.** Без количеств процент
 * врёт умолчанием: лауроилглутамат «подорожал на 278 %», но 19.07 пришло
 * 5 000 г по 0,45 ₽, а 05.08 — 1 000 г по 1,70 ₽. Партия впятеро меньше,
 * и это часть ответа, а не мелочь из раскрытия строки.
 */
export function PriceChange({
  change,
  previous,
  last,
  previousQuantity,
  lastQuantity,
  uom,
}: {
  change: string | null
  previous: string | null
  last: string | null
  /** Партии, из которых взяты цены. Без них процент читается как чистое подорожание. */
  previousQuantity?: string | null
  lastQuantity?: string | null
  uom?: string
}) {
  if (change === null) {
    // Прочерк, а не ноль: ноль означал бы «цена не менялась», а здесь
    // сравнивать не с чем — закупка была одна.
    return <span className="text-muted-foreground">—</span>
  }

  const value = Number(change)
  const Icon = value > 0 ? TrendingUp : value < 0 ? TrendingDown : Minus

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            className={cn(
              "inline-flex cursor-help items-center gap-1 tabular-nums",
              value > 0 && "font-medium text-destructive",
              value < 0 && "font-medium text-success",
              value === 0 && "text-muted-foreground"
            )}
          >
            <Icon aria-hidden className="size-3.5 shrink-0" />
            {/* Знак у нуля лишний: «0,0 %» и так значит «не менялась». */}
            {value === 0 ? formatShare("0") : formatShare(String(Math.abs(value)))}
          </span>
        }
      />
      <TooltipContent className="font-normal tabular-nums">
        {side(previous, previousQuantity, uom)} → {side(last, lastQuantity, uom)}
      </TooltipContent>
    </Tooltip>
  )
}

/** Одна сторона сравнения: «5 000 г по 0,45 ₽» или просто цена. */
function side(
  price: string | null,
  quantity: string | null | undefined,
  uom?: string
): string {
  const value = formatUnitPrice(price)
  if (!quantity) return value
  return `${formatQuantity(quantity, uom)} по ${value}`
}
