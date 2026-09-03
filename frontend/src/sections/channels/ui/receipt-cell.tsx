import type { Receipt } from "@/sections/channels/api"
import { formatMoney } from "@/shared/lib/format"

/**
 * Средний чек канала вместе со шкалой разброса.
 *
 * **Одно число здесь врёт.** У «Точки продаж» медиана 2 771,63 ₽, а отгрузки
 * идут от нуля до 99 495,50 ₽: «обычно две с половиной тысячи» — правда,
 * но канал держится не на них. Поэтому под числом всегда стоят границы:
 * медиана без разброса врёт, и это правило проекта, а не украшение строки.
 *
 * **Отрезок отсюда убран 03.09** по решению владельца: рисунок внутри
 * ячейки был третьим уровнем содержимого в клетке и ломал ритм строк.
 * Границы остались текстом — терять их было нельзя.
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
 * Границы под медианой: от самой мелкой отгрузки до самой крупной.
 *
 * Не «сколько обычно», а «насколько это „обычно“ вообще существует».
 * У «Точки продаж» медиана 2 771,63 ₽ при отгрузке на 99 495,50 ₽ — и без
 * второй строки первая читается как описание канала целиком.
 */
function Scale({ receipt }: { receipt: Receipt }) {
  const { min_kopecks: min, max_kopecks: max, kopecks: median } = receipt
  if (min === null || max === null || median === null) return null

  // Разброса нет вовсе: все отгрузки на одну сумму. Диапазон соврал бы
  // про неопределённость, которой здесь нет.
  if (min === max) {
    return (
      <span className="text-xs text-muted-foreground">
        {receipt.shipments === 1 ? "одна отгрузка" : "без разброса"}
      </span>
    )
  }

  return (
    <span className="text-xs text-muted-foreground tabular-nums">
      {min === 0 ? "от нуля" : `от ${formatMoney(min)}`} до {formatMoney(max)}
    </span>
  )
}
