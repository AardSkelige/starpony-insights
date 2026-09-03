import { formatDays } from "@/sections/suppliers/days"
import type { components } from "@/shared/api/schema"

type Span = components["schemas"]["Regularity"] | components["schemas"]["LeadTime"]

/**
 * Медиана в днях вместе со шкалой разброса.
 *
 * **Одно число здесь врёт.** У «Ревады-Невы» срок 21 день сложился из двух
 * поставок — 2 и 40; у «Спецума» интервал 68 дней — из 2 и 134. Медиана
 * честно отвечает «сколько обычно», но «обычно» у них не существует,
 * и без разброса рядом это не видно.
 *
 * Поэтому под числом всегда стоят границы: «21 день» и «2–40» рядом
 * говорят разное, и второе важнее. Правило проекта, а не украшение строки.
 *
 * **Отрезок отсюда убран 03.09** по решению владельца: рисунок внутри
 * ячейки был третьим уровнем содержимого в клетке и ломал ритм строк.
 * Границы остались текстом, а сам разброс целиком — в разборе строки,
 * блоками «Срок поставки» и «Ритм поставок».
 */
export function SpanCell({
  span,
  zeroLabel,
  emptyLabel,
}: {
  span: Span
  /**
   * Что писать вместо «0 дн». У срока поставки это «в тот же день»:
   * ноль там ответ, а не пробел — у «Принтеца» и «Интернет Решений»
   * забирают, а не ждут доставку.
   */
  zeroLabel?: string
  /** Почему мерить было нечего: «поставка одна» у регулярности. */
  emptyLabel: string
}) {
  if (span.days === null) {
    return (
      <span className="flex flex-col items-end gap-1">
        <span className="text-muted-foreground">—</span>
        <span className="text-xs text-muted-foreground">{emptyLabel}</span>
      </span>
    )
  }

  const days = Number(span.days)

  return (
    <span className="flex flex-col items-end gap-1">
      <span>{days === 0 && zeroLabel ? zeroLabel : formatDays(days)}</span>
      <Scale span={span} />
    </span>
  )
}

/**
 * Границы под медианой: от самого короткого промежутка до самого длинного.
 *
 * Не «сколько обычно», а «насколько это „обычно“ вообще существует».
 * У «Ревады-Невы» 21 день сложился из 2 и 40 — и без второй строки первая
 * читается как обещание.
 */
function Scale({ span }: { span: Span }) {
  if (span.min_days === null || span.max_days === null) return null

  const { min_days: min, max_days: max } = span

  // Разброса нет вовсе: все промежутки одинаковые. Диапазон «21–21»
  // соврал бы про неопределённость, которой здесь нет.
  if (min === max) {
    return (
      <span className="text-xs text-muted-foreground">
        {span.measurements === 1 ? "одно измерение" : "без разброса"}
      </span>
    )
  }

  return (
    <span className="text-xs text-muted-foreground tabular-nums">
      {min}–{max}
    </span>
  )
}

