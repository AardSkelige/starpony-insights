import type { Receipt } from "@/sections/channels/api"
import { formatMoney } from "@/shared/lib/format"

/**
 * Средний чек канала вместе со шкалой разброса.
 *
 * **Одно число здесь врёт.** У «Точки продаж» медиана 2 771,63 ₽, а отгрузки
 * идут от нуля до 99 495,50 ₽: «обычно две с половиной тысячи» — правда,
 * но канал держится не на них. Отрезок под числом показывает то, чего числом
 * не сказать, и разница между ровным каналом и рваным читается не глядя
 * на цифры.
 *
 * **Ноль — ответ, а не прочерк.** У Instagram и Telegram медиана ровно ноль:
 * больше половины отгрузок ушли даром. Подпись под числом говорит об этом
 * прямо, иначе «0,00 ₽» читается как сбой расчёта.
 *
 * Прочерк остаётся каналу, у которого отгрузок в периоде не было вовсе.
 */
export function ReceiptCell({ receipt }: { receipt: Receipt }) {
  if (receipt.kopecks === null) {
    return (
      <span className="flex flex-col items-end gap-1">
        <span className="text-muted-foreground">—</span>
        <span className="text-xs text-muted-foreground">не продавали</span>
      </span>
    )
  }

  return (
    <span className="flex flex-col items-end gap-1">
      <span>{formatMoney(receipt.kopecks)}</span>
      {receipt.kopecks === 0 ? (
        <span className="text-xs text-muted-foreground">
          {receipt.free_shipments} из {receipt.shipments} даром
        </span>
      ) : (
        <Scale receipt={receipt} />
      )}
    </span>
  )
}

/**
 * Полоса min–max и метка медианы.
 *
 * Ширина отсчитывается от нуля до максимума **этой строки**, а не от общего
 * максимума таблицы. Общий сделал бы почти все полосы неразличимо короткими:
 * у «Точки продаж» максимум 99 495 ₽, у Озона — 9 173 ₽. Вопрос строки —
 * «ровно ли продаёт этот канал», а не «у кого чек крупнее»: на второе
 * отвечает само число рядом.
 */
function Scale({ receipt }: { receipt: Receipt }) {
  const { min_kopecks: min, max_kopecks: max, kopecks: median } = receipt
  if (min === null || max === null || median === null) return null

  // Разброса нет вовсе: все отгрузки на одну сумму. Полоса во всю ширину
  // соврала бы про неопределённость, которой здесь нет.
  if (min === max) {
    return (
      <span className="text-xs text-muted-foreground">
        {receipt.shipments === 1 ? "одна отгрузка" : "без разброса"}
      </span>
    )
  }

  // Дорожка отсчитывается от нуля, а не от минимума: полоса, начинающаяся
  // у левого края, означает «случалось и даром», и это половина смысла
  // рисунка — на боевых данных таких отгрузок 46 из 306.
  const at = (value: number) => clamp((value / max) * 100)

  return (
    <span className="flex items-center gap-1.5">
      <span
        aria-hidden
        className="relative h-1 w-10 shrink-0 rounded-full bg-muted lg:w-16"
      >
        <span
          className="absolute inset-y-0 rounded-full bg-primary/25"
          style={{ left: `${at(min)}%`, right: 0 }}
        />
        {/* Метка медианы: два пикселя, но выше полосы — иначе она теряется
            внутри заливки того же семейства цветов. */}
        <span
          className="absolute -top-0.5 h-2 w-0.5 rounded-full bg-primary"
          style={{ left: `${at(median)}%` }}
        />
      </span>
      <span className="text-xs text-muted-foreground tabular-nums">
        до {formatMoney(max)}
      </span>
    </span>
  )
}

/** Ничто не должно уезжать за края дорожки, что бы ни пришло с сервера. */
function clamp(percent: number): number {
  return Math.min(Math.max(percent, 0), 99)
}
