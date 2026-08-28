import { Fact, Facts, Failed, Loading, Section } from "@/shared/components/detail"
import type { Stock } from "@/shared/api/types"
import { formatQuantity } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Блок «Склад» в разборе строки — общий для всех разделов.
 *
 * Раньше он был написан дважды, по разу на страницу, и копии разошлись:
 * у товаров не доехавший ответ рисовался как «остатка нет» — то есть сбой
 * связи выдавался за факт учёта, — а дни без движения не склонялись.
 * Это и есть цена второй копии: чинят одну, вторая молча остаётся с багом.
 *
 * Принимает результат запроса деталей целиком, а не разобранные поля:
 * состояний у блока четыре — «едет», «не доехало», «остатка нет», «вот он», —
 * и каждое из них должно выглядеть по-своему.
 *
 * О сбое и о пустоте блок говорит, только когда он **один в своём месте**
 * (`bare` — то есть за собственной вкладкой). Рядом с соседями он молчит:
 * разбор строки собран из блоков одного запроса, и жалуйся каждый — человек
 * получил бы три одинаковых «Не удалось загрузить» с тремя кнопками, которые
 * повторяют один и тот же запрос.
 */
type StockDetail = {
  isPending: boolean
  isError: boolean
  refetch: () => void
  data?: { stock: Stock | null }
}

export function StockSection({
  detail,
  uom,
  bare = false,
  emptyNote,
}: {
  detail: StockDetail
  /** Единица измерения строки: у сырья остаток в граммах, у товара в штуках. */
  uom?: string
  /** За вкладкой заголовок лишний — его роль играет сама вкладка. */
  bare?: boolean
  /**
   * Что сказать, когда остатка нет вовсе. Показывается только за вкладкой.
   *
   * Формулировка — знание раздела: у материалов «в отчёте МойСклада его нет»,
   * и это факт учёта, а не поломка.
   */
  emptyNote?: string
}) {
  if (detail.isError) {
    // Молча исчезнуть можно только рядом с соседями: за своей вкладкой
    // пустота читается как поломка страницы, а не как «данные не доехали».
    if (!bare) return null
    return (
      <Section title="Склад" bare>
        <Failed onRetry={() => detail.refetch()} />
      </Section>
    )
  }

  if (detail.isPending) {
    return (
      <Section title="Склад" bare={bare}>
        <Loading count={2} />
      </Section>
    )
  }

  const stock = detail.data?.stock

  // Нули вместо остатка читались бы как «кончился», поэтому блока просто нет —
  // кроме случая, когда ему отведена своя вкладка и пустота выглядит сбоем.
  if (!stock) {
    if (!emptyNote) return null
    return (
      <Section title="Склад" bare={bare}>
        <p className="py-1.5 text-sm text-muted-foreground">{emptyNote}</p>
      </Section>
    )
  }

  return (
    <Section title="Склад" bare={bare}>
      <Facts>
        <Fact label="Остаток" value={formatQuantity(stock.quantity, uom)} />
        <Fact label="В резерве" value={formatQuantity(stock.reserved)} />
        <Fact label="Свободно" value={formatQuantity(stock.available)} />
        {stock.stock_days !== null ? (
          <Fact
            label="Без движения"
            value={withPlural(stock.stock_days, "день", "дня", "дней")}
          />
        ) : null}
      </Facts>
    </Section>
  )
}
