import type {
  SupplyMaterialRow,
  SupplyMaterials,
} from "@/sections/supplies-materials/api"
import { PriceSpark } from "@/sections/supplies-materials/ui/price-line"
import { PriceChange } from "@/sections/supplies-materials/ui/price-change"
import type { Column, Totals } from "@/shared/components/data-table"
import { Explain } from "@/shared/components/explain"
import { formatMoney, formatQuantity, formatUnitPrice } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Колонки таблицы «Материалы в приёмках».
 *
 * Шесть колонок, а не девять: средняя цена, доля и число поставщиков живут
 * в раскрытии строки. Причина — «Динамика» должна оставаться видимой
 * на ноутбуке: это главный вопрос страницы, и спрячься она первой,
 * страница потеряла бы смысл на самом частом экране.
 *
 * Прочерк вместо нуля там, где величины нет: у 24 наименований из 212 цены
 * нет вовсе (приходили только даром), у 130 нет предыдущей закупки. Ноль
 * читался бы как «бесплатный материал» и «цена не менялась» — оба
 * утверждения были бы ложью об учёте.
 */
export const COLUMNS: Column<SupplyMaterialRow>[] = [
  {
    key: "name",
    label: "Материал",
    sortKey: "name",
    changeValue: (row) => [row.name, row.code, row.article],
    render: (row) => (
      <span className="flex min-w-0 flex-col">
        {/* Название переносится в две строки, а не обрезается в одну:
            «Этикетка | Задняя | Кондиционер для гривы и хвоста Peachy
            Banana 500 мл (Старое)», обрезанное после «для гривы и хвост…»,
            не отличить от такой же этикетки другого запаха. Самое длинное
            наименование в учёте — 84 знака, и в две строки оно входит
            целиком. На телефоне ограничения нет вовсе: там строка карточки
            занимает всю ширину.

            `whitespace-normal` обязателен вместе с `line-clamp-2`:
            `TableCell` из реестра объявляет `whitespace-nowrap`, и без отмены
            переносить нечего — текст остаётся одной строкой, а `line-clamp`
            просто обрезает её многоточием. */}
        <span className="line-clamp-2 whitespace-normal max-sm:line-clamp-none max-sm:font-medium">
          {row.name}
        </span>
        <span className="truncate font-mono text-xs text-muted-foreground">
          {[row.code, row.article].filter(Boolean).join(" · ")}
        </span>
      </span>
    ),
  },
  {
    key: "quantity",
    label: "Закуплено",
    numeric: true,
    sortKey: "quantity",
    changeValue: (row) => [
      row.quantity,
      row.uom,
      row.free_quantity,
      row.paid_quantity,
      row.mixed_uom,
    ],
    render: (row) => (
      <span className="flex flex-col items-end">
        <span>{formatQuantity(row.quantity, row.uom)}</span>
        {/* Подстрочник, а не отдельная колонка: даром приходило только
            у 42 наименований из 212, и колонка пустовала бы у остальных 170. */}
        {Number(row.free_quantity) > 0 ? (
          <span className="text-xs text-muted-foreground">
            {Number(row.paid_quantity) > 0
              ? `в т.ч. ${formatQuantity(row.free_quantity)} даром`
              : "всё даром"}
          </span>
        ) : null}
        {/* Материал, пришедший в разных единицах, складывать нельзя:
            килограмм против грамма ошибается ровно в тысячу раз. */}
        {row.mixed_uom ? (
          <span className="text-xs text-warning">разные единицы</span>
        ) : null}
      </span>
    ),
    explain: (
      <Explain>
        Сколько пришло на склад за период. Подстрочником — сколько из этого
        досталось <b>даром</b>: образцы, бонусы поставщика, допечатка этикеток.
        Из количества оно не вычтено — на складе лежит, — но в цену не входит.
      </Explain>
    ),
  },
  {
    key: "amount",
    label: "Сумма",
    numeric: true,
    sortKey: "amount",
    changeValue: (row) => row.amount_kopecks,
    render: (row) =>
      row.amount_kopecks > 0 ? (
        formatMoney(row.amount_kopecks)
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
    explain: (
      <Explain>
        <b>Сумма всех приёмок материала за период</b> — как в документах,
        до копейки. Прочерк там, где материал приходил только даром:
        ноль читался бы как «бесплатный».
      </Explain>
    ),
  },
  {
    key: "price",
    label: "Цена",
    numeric: true,
    sortKey: "last_price",
    changeValue: (row) => [row.prices, row.last_price_kopecks, row.uom],
    render: (row) => (
      <span className="flex items-center justify-end gap-2">
        <PriceSpark prices={row.prices} />
        {row.last_price_kopecks === null ? (
          <span className="text-muted-foreground">—</span>
        ) : (
          <span>
            {formatUnitPrice(row.last_price_kopecks)}/{row.uom || "ед."}
          </span>
        )}
      </span>
    ),
    explain: (
      <Explain>
        <b>Цена последней закупки</b> и весь ряд цен за период линией.
        Линия строится <b>по времени</b>, а не по номеру закупки: равные
        промежутки соврали бы о том, как быстро материал дорожает. У одной
        закупки линии нет — рисовать нечего.
      </Explain>
    ),
  },
  {
    key: "change",
    label: "Динамика",
    numeric: true,
    sortKey: "change",
    changeValue: (row) => [
      row.price_change,
      row.previous_price_kopecks,
      row.last_price_kopecks,
      row.previous_quantity,
      row.last_quantity,
      row.uom,
    ],
    render: (row) => (
      <PriceChange
        change={row.price_change}
        previous={row.previous_price_kopecks}
        last={row.last_price_kopecks}
        previousQuantity={row.previous_quantity}
        lastQuantity={row.last_quantity}
        uom={row.uom}
      />
    ),
    explain: (
      <Explain>
        <b>Последняя цена ÷ предыдущая − 1.</b> Отвечает на «подорожало ли
        в этот раз»: у флакона 25,05 → 26,76 → 31,05, и к первой цене вышло
        бы +24 %, скрыв, что последний шаг +16 %. Весь ряд — в раскрытии
        строки. Прочерк у 130 наименований из 212: закупка была одна,
        сравнивать не с чем.
      </Explain>
    ),
  },
  {
    key: "supplies",
    label: "Закупок",
    cardLabel: "Закупок за период",
    numeric: true,
    sortKey: "supplies",
    hideOn: ["narrow"],
    changeValue: (row) => [row.supplies_count, row.suppliers_count],
    render: (row) => (
      <span className="flex flex-col items-end">
        <span>{String(row.supplies_count)}</span>
        {row.suppliers_count > 1 ? (
          <span className="text-xs text-muted-foreground">
            у {withPlural(row.suppliers_count, "поставщика", "поставщиков", "поставщиков")}
          </span>
        ) : null}
      </span>
    ),
    explain: (
      <Explain>
        <b>Закупка — это приёмка, а не строка в ней.</b> Один материал приходит
        одним документом двумя партиями: считай мы строками, у диметилфталата
        оказалось бы шесть закупок вместо пяти и скачок цены внутри одного дня.
      </Explain>
    ),
  },
]

/**
 * По чему эта таблица умеет сортировать — выводится из самих колонок.
 *
 * Второй список неизбежно разъехался бы с первым: колонку добавляют,
 * а перечень ключей забывают — и ссылка с новым порядком приходит
 * к экрану ошибки вместо таблицы.
 */
export const SORT_KEYS: readonly string[] = COLUMNS.flatMap((column) =>
  column.sortKey ? [column.sortKey] : []
)

/**
 * Итог по всей выборке, а не по видимой странице.
 *
 * Живёт рядом с колонками, а не на странице: подвал задаётся **их ключами**,
 * и опечатка в ключе даёт пустую ячейку молча — таблица не падает, просто
 * итог не показывается.
 *
 * У количества итога нет намеренно: сложить граммы со штуками нельзя,
 * а число под колонкой, где вперемешку то и другое, ничего не значит.
 * У цены и динамики — тем более: средняя из средних не значит ничего.
 */
export function totalsFor(totals: SupplyMaterials["totals"]): Totals {
  return {
    label: `Итого · ${withPlural(totals.materials_count, "материал", "материала", "материалов")}`,
    values: {
      quantity: <span className="text-muted-foreground">разные единицы</span>,
      amount: formatMoney(totals.amount_kopecks),
      price: <span className="text-muted-foreground">—</span>,
      change: <span className="text-muted-foreground">—</span>,
      supplies: <span className="text-muted-foreground">—</span>,
    },
  }
}
