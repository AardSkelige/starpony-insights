import type { BatchLine } from "@/sections/production/api"
import { WarningStrip } from "@/shared/components/warning-strip"
import { withPlural } from "@/shared/lib/plural"

/**
 * Строки партии, не попавшие в расчёт.
 *
 * **Не выбрасываются молча ни в одном случае.** Сломанная ссылка и опечатка
 * в артикуле выглядят одинаково, а «посчитали по трём товарам из четырёх»
 * ничем не отличается на вид от «посчитали по всем» — и разница обнаружится
 * на складе, когда сырья не хватит.
 *
 * Четыре причины, и они разные. «В архиве» — не «не найден»: товар
 * существует, человек его помнит, и «не найден» отправил бы его искать то,
 * что он видит. «Нет техкарты» — не ошибка ввода вовсе, а пробел в учёте:
 * рассчитать такой товар не из чего, пока карту не заведут. «Впишите сами» —
 * и не ошибка, и не пробел: товар годен, просто предложить количество
 * не из чего, и человеку достаточно набрать его руками.
 */

const REASON: Record<string, string> = {
  unknown: "артикула нет в учёте",
  archived: "товар в архиве — его больше не выпускают",
  no_plan: "нет техкарты — рассчитать не из чего",
  // Отмечен, а количество предложить не из чего: не продавался за период
  // либо остаток неизвестен. Раньше такая позиция выпадала из расчёта
  // молча — галочка стояла, а в партии её не было.
  no_quantity: "сколько произвести — впишите сами: продаж за период нет "
    + "либо остаток неизвестен",
}

export function Problems({ lines }: { lines: BatchLine[] }) {
  const bad = lines.filter((line) => line.problem !== null)
  if (!bad.length) return null

  return (
    <WarningStrip>
      <span className="font-medium">
        {withPlural(bad.length, "позиция", "позиции", "позиций")} партии
        не посчитана.
      </span>{" "}
      <span className="text-muted-foreground">
        {bad.map((line, index) => (
          <span key={line.article}>
            {index > 0 ? "; " : ""}
            {line.name || line.article}
            {line.name ? ` (${line.article})` : ""} —{" "}
            {REASON[line.problem!] ?? line.problem}
          </span>
        ))}
        .
      </span>
    </WarningStrip>
  )
}
