import type { Home } from "@/sections/home/api"
import { withMonth } from "@/sections/home/links"
import { pulseRemark } from "@/sections/home/remarks"
import { Figure } from "@/sections/home/ui/figure"
import { Months } from "@/sections/home/ui/months"
import { Tile } from "@/sections/home/ui/tile"
import { Explain } from "@/shared/components/explain"
import { formatMoney } from "@/shared/lib/format"

/**
 * «Пульс»: как идут дела в сравнении с прошлым месяцем.
 *
 * **Два множества разведены по группам, и это главное решение плитки.**
 * «Отгружено» — документы: сколько увезли со склада. «Продано» — отчёт
 * прибыльности: сколько из увезённого стало выручкой. По договору комиссии
 * товар становится проданным только с приходом отчёта комиссионера, поэтому
 * второе меньше первого.
 *
 * Поставь мы их в один ряд — человек поделил бы выручку отгрузок
 * на себестоимость продаж и получил бы маржу, которой нет. Ровно тот дефект,
 * который на трёх страницах ловили как «соседние числа о разных множествах»
 * (`DESIGN.md` §8). Разница названа отдельной строкой, а не оставлена
 * на вычитание.
 */
export function PulseTile({ data, period }: {
  data: NonNullable<Home["pulse"]>
  period: Home["period"]
}) {
  return (
    <Tile
      title="Пульс"
      window={`${period.label} к ${period.earlier_label_to}`}
      windowNote="полные месяцы, идущий в сравнение не входит"
      link={{ to: withMonth("/shipments/products", period), label: "Разобрать" }}
      remark={pulseRemark(data) ?? undefined}
    >
      <div className="flex flex-col gap-4">
        <section>
          <h3 className="mb-2 text-xs font-medium text-muted-foreground">
            Отгружено — что увезли со склада
          </h3>
          <div className="grid grid-cols-1 gap-x-5 gap-y-3 @xs:grid-cols-2 @lg:grid-cols-3">
            {data.shipped.map((figure) => (
              <Figure key={figure.key} figure={figure} />
            ))}
          </div>
        </section>

        <section className="border-t pt-3">
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            Продано — что стало выручкой
            <Explain>
              Из отчёта прибыльности МойСклада. Меньше отгруженного, потому что
              товар по договору комиссии становится проданным только с приходом
              отчёта комиссионера. Оба числа верны — они отвечают на разные
              вопросы, и складывать их нельзя.
            </Explain>
          </h3>
          <div className="grid grid-cols-1 gap-x-5 gap-y-3 @xs:grid-cols-2 @lg:grid-cols-3">
            {data.sold.map((figure) => (
              <Figure key={figure.key} figure={figure} />
            ))}
          </div>
          {data.consignment_kopecks > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Разница {formatMoney(data.consignment_kopecks)} — товар уехал,
              но ещё не продан: лежит у комиссионеров.
            </p>
          ) : null}
        </section>

        {data.months.length > 1 ? (
          <section className="border-t pt-3">
            <Months months={data.months} />
            {period.running_label ? (
              <p className="mt-1.5 text-xs text-muted-foreground">
                Бледный столбик — незаконченный месяц.
              </p>
            ) : null}
          </section>
        ) : null}
      </div>
    </Tile>
  )
}
