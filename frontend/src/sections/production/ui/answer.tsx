import type { BatchSummary } from "@/sections/production/api"
import { approxRubles } from "@/sections/production/ui/money"
import { Explain } from "@/shared/components/explain"
import { withPlural } from "@/shared/lib/plural"

/**
 * Итог партии — то, ради чего страницу открывали.
 *
 * Три числа, и каждое требует действия: сколько докупить, сколько ждать,
 * сколько варить. Показатель, по которому решения не принимают, сюда
 * не добавляется (`DESIGN.md` §7): «43 материала» — шум, «докупить
 * на 116,64 ₽» — по этому звонят поставщику.
 *
 * **Крупно и с цветом только там, где пора действовать.** Ноль недостающих
 * позиций — это хорошая новость, и красить её красным значило бы обесценить
 * красный там, где он настоящий.
 */
export function Answer({ summary }: { summary: BatchSummary }) {
  const nothing = summary.products_count === 0
  // Нехватки нет, но по части материалов остатка в отчёте нет вовсе —
  // и «ничего» тогда неправда: мы не знаем, а не убедились. Список ниже
  // как раз показывает эти строки, и «докупить ничего» рядом с ними
  // читалось как противоречие.
  const blind = summary.shortages_count === 0 && summary.unknown_stock_count > 0

  return (
    <div className="flex flex-wrap items-end gap-x-8 gap-y-4 rounded-lg border bg-card p-4">
      <Figure
        label="Произвести"
        value={nothing ? "—" : `${summary.units_count} шт`}
        note={
          nothing
            ? "отметьте товары слева"
            : withPlural(summary.products_count, "товар", "товара", "товаров")
        }
      />

      <Figure
        label="Докупить"
        explain="Сколько позиций сырья придётся докупить: по каждой нужно на партию больше, чем лежит на складе. Рубли рядом — прикидка по ценам последних закупок: заказывают упаковками, а не граммами, и точную сумму даст только счёт поставщика."
        // Позиции, а не рубли: по «докупить 2 позиции» звонят поставщику,
        // а по «2 790,78 ₽» — ничего. Сумма получена умножением нехватки
        // на цену за единицу, но закупают упаковками, и копейки в ней
        // изображают точность, которой нет (замечание владельца 03.09).
        value={
          summary.shortages_count > 0
            ? withPlural(
                summary.shortages_count,
                "позиция",
                "позиции",
                "позиций"
              )
            : blind
              ? "не знаем"
              : "ничего"
        }
        tone={
          summary.shortages_count > 0
            ? "text-destructive"
            : blind
              ? "text-muted-foreground"
              : undefined
        }
        note={
          summary.shortages_count > 0
            ? // Сумма — итог по тем, у кого известна цена, а не по всем
              // недостающим. Без этой оговорки она читается как полная
              // стоимость закупки (`DESIGN.md` §8).
              summary.priced_shortages_count === 0
              ? "цен последних закупок нет"
              : summary.priced_shortages_count === summary.shortages_count
                ? `${approxRubles(summary.purchase_kopecks)} по ценам закупок`
                : `${approxRubles(summary.purchase_kopecks)} по ${
                    summary.priced_shortages_count
                  } из ${summary.shortages_count} с ценой`
            : blind
              ? `по ${withPlural(
                  summary.unknown_stock_count,
                  "позиции",
                  "позициям",
                  "позициям"
                )} остатка нет в отчёте`
              : nothing
                ? "партия не собрана"
                : "сырья хватает на всю партию"
        }
      />

      <Figure
        label="Ждать"
        explain="Самый долгий срок среди недостающего: партия начнётся не раньше, чем приедет последний материал. Срок — медиана дней «заказ → приёмка» у того поставщика, у которого материал брали в последний раз. Там, где материал ни разу не покупали, поставщик неизвестен — и срок тоже; такие позиции в это число не входят и посчитаны отдельно."
        value={
          summary.max_lead_time_days === null
            ? "—"
            : withPlural(
                Math.round(Number(summary.max_lead_time_days)),
                "день",
                "дня",
                "дней"
              )
        }
        note={
          summary.max_lead_time_days === null
            ? "сроков поставки нет"
            : // Знаменатель обязателен: срок известен только там, где
              // известен поставщик, а он берётся из последней приёмки
              // (`DESIGN.md` §8).
              summary.timed_shortages_count === summary.shortages_count
              ? "пока приедет последнее"
              : `по ${summary.timed_shortages_count} из ${
                  summary.shortages_count
                } — у остальных срок неизвестен`
        }
      />
    </div>
  )
}

function Figure({
  label,
  value,
  note,
  tone,
  explain,
}: {
  label: string
  value: string
  note: string
  tone?: string
  explain?: string
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 text-xs tracking-wide text-muted-foreground uppercase">
        {label}
        {explain ? <Explain>{explain}</Explain> : null}
      </div>
      {/* Число не ужимается — уступает подпись: `shrink-0` на значении,
          `min-w-0` на тексте рядом (`DESIGN.md` §15). */}
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${tone ?? ""}`}>
        {value}
      </div>
      <div className="text-xs text-muted-foreground">{note}</div>
    </div>
  )
}
