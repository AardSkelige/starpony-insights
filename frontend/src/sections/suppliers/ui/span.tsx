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
 * Отрезок показывает то, чего числом не сказать: полоса от минимума
 * до максимума и метка медианы на ней. «Спецум» рисуется во всю ширину,
 * «Тара.ру» с её 35–92 при медиане 40 — коротким штрихом справа. Разница
 * читается не глядя на цифры, а это и есть ответ на «кому можно верить».
 *
 * Шкала общая для обеих величин, и это намеренно: у регулярности и срока
 * поставки один вид, потому что вопрос у них один — насколько ровно.
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
 * Сама шкала: полоса min–max и метка медианы.
 *
 * Ширина отсчитывается от нуля до максимума этой строки, а не от общего
 * максимума таблицы. Общий сделал бы почти все полосы неразличимо короткими:
 * у «Спецума» максимум 134 дня, у половины поставщиков — меньше десяти.
 * Вопрос строки — «ровно ли возит этот», а не «кто дольше всех».
 */
function Scale({ span }: { span: Span }) {
  if (span.min_days === null || span.max_days === null) return null

  const { min_days: min, max_days: max } = span
  const days = Number(span.days)

  // Разброса нет вовсе: все промежутки одинаковые. Полоса во всю ширину
  // соврала бы про неопределённость, которой здесь нет.
  if (min === max) {
    return (
      <span className="text-xs text-muted-foreground">
        {span.measurements === 1 ? "одно измерение" : "без разброса"}
      </span>
    )
  }

  // Дорожка отсчитывается от нуля, а не от минимума: полоса, начинающаяся
  // у левого края, означает «случалось и сразу», и это половина смысла
  // рисунка. Отрицательный минимум бывает — заказ, оформленный после
  // прихода товара, даёт минус, и тогда началом становится он: иначе
  // `min / max` уводит полосу за пределы дорожки, а при `max` равном нулю
  // даёт бесконечность, и вся шкала исчезает без единого признака.
  const floor = Math.min(0, min)
  const width = max - floor
  const at = (value: number) => clamp(((value - floor) / width) * 100)

  const left = at(min)
  const marker = at(days)

  return (
    <span className="flex items-center gap-1.5">
      <span
        aria-hidden
        // Уже на узком экране: там колонок пять из восьми, и каждые
        // сэкономленные точки достаются имени поставщика, которое иначе
        // обрезается многоточием.
        className="relative h-1 w-10 shrink-0 rounded-full bg-muted lg:w-16"
      >
        <span
          className="absolute inset-y-0 rounded-full bg-primary/25"
          style={{ left: `${left}%`, right: 0 }}
        />
        {/* Метка медианы: два пикселя, но выше полосы — иначе она теряется
            внутри заливки того же семейства цветов. */}
        <span
          className="absolute -top-0.5 h-2 w-0.5 rounded-full bg-primary"
          style={{ left: `${marker}%` }}
        />
      </span>
      <span className="text-xs text-muted-foreground tabular-nums">
        {min}–{max}
      </span>
    </span>
  )
}

/** Ничто не должно уезжать за края дорожки, что бы ни пришло с сервера. */
function clamp(percent: number): number {
  return Math.min(Math.max(percent, 0), 99)
}

