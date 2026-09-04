import { Explain } from "@/shared/components/explain"
import type { Column, Totals } from "@/shared/components/data-table"
import type {
  ShipmentProductRow,
  ShipmentProducts,
} from "@/sections/shipments-products/api"
import {
  formatMoney,
  formatQuantity,
  formatShare,
  formatUnitPrice,
} from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Колонки таблицы «Товары в отгрузках».
 *
 * Маржи здесь нет намеренно: себестоимость на дату отгрузки в учёт не
 * выгружается, а считать её по сегодняшнему остатку — тихо соврать.
 * Она появится в разделе «Прибыльность» вместе со своим полем в синхронизации.
 */
export const COLUMNS: Column<ShipmentProductRow>[] = [
  {
    key: "name",
    label: "Наименование",
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
    label: "Продано",
    numeric: true,
    sortKey: "quantity",
    changeValue: (row) => [row.quantity, row.uom],
    render: (row) => formatQuantity(row.quantity, row.uom),
    explain: (
      <Explain>
        Сумма количеств по всем позициям отгрузок за период. Взято из учёта
        как есть, не рассчитано.
      </Explain>
    ),
  },
  {
    key: "free",
    label: "в т.ч. даром",
    cardLabel: "Даром",
    numeric: true,
    sortKey: "free",
    // На узком экране прячется первой: это важное число, но не то, ради
    // которого открывают страницу.
    hideOn: ["narrow"],
    changeValue: (row) => row.free_quantity,
    // Единица обязательна: колонка самостоятельная, и «105» рядом
    // с «431 шт» читалось как другая величина, хотя это те же штуки.
    render: (row) =>
      Number(row.free_quantity) > 0
        ? formatQuantity(row.free_quantity, row.uom)
        : "—",
    explain: (
      <Explain>
        Сколько штук ушло по позициям с суммой 0 ₽ — образцы, замены, подарки.
        Со склада списано, выручки нет. Природа таких отгрузок в учёте
        не размечена, поэтому они показаны отдельно, а не смешаны с продажами.
      </Explain>
    ),
  },
  {
    key: "revenue",
    label: "Выручка",
    numeric: true,
    sortKey: "revenue",
    changeValue: (row) => row.revenue_kopecks,
    render: (row) => formatMoney(row.revenue_kopecks),
    explain: (
      <Explain>
        Сумма строк отгрузок за период — как в документах учёта, до копейки.
      </Explain>
    ),
  },
  {
    key: "avg",
    label: "Средняя цена продажи",
    cardLabel: "Средняя цена",
    numeric: true,
    sortKey: "avg_price",
    changeValue: (row) => row.avg_price_kopecks,
    render: (row) => formatUnitPrice(row.avg_price_kopecks),
    explain: (
      <Explain>
        <b>Выручка ÷ продано.</b> В количество входит и отгруженное за 0 ₽,
        поэтому цена ниже прейскурантной. Цена без учёта бесплатных штук
        показана в раскрытии строки.
      </Explain>
    ),
  },
  {
    key: "card_price",
    label: "Цена в карточке",
    cardLabel: "Цена в карточке",
    numeric: true,
    sortKey: "card_price",
    // `hideOn` здесь нет намеренно: главная присылает сюда сигналом
    // с сортировкой по этой колонке, и спрятать её на узком экране значит
    // открыть страницу, отсортированную по невидимому столбцу, — без единого
    // признака почему.
    
    changeValue: (row) => row.card_price_kopecks,
    render: (row) =>
      row.card_price_kopecks === null ? (
        // Строки остатка нет — товара на складе не было, и вопроса о его
        // цене не стоит. Не то же самое, что цена не задана.
        <span className="text-muted-foreground">—</span>
      ) : Number(row.card_price_kopecks) === 0 ? (
        // А вот это уже сигнал: товар лежит, а продать его нельзя.
        // Цветом и словами сразу — `DESIGN.md` §1.
        <span className="text-destructive">не задана</span>
      ) : (
        formatUnitPrice(row.card_price_kopecks)
      ),
    explain: (
      <Explain>
        <b>Цена продажи из карточки МойСклада</b> — рядом с фактической,
        по которой продавали. Расхождение между ними видно только когда обе
        стоят рядом: продавали дешевле прайса или дороже, замечают именно так.
        «Не задана» — товар лежит на складе, а продать его нельзя; прочерк —
        товара на складе нет, и вопроса о цене не возникает.
      </Explain>
    ),
  },
  {
    key: "share",
    label: "Доля в выручке",
    cardLabel: "Доля",
    numeric: true,
    sortKey: "share",
    hideOn: ["narrow"],
    changeValue: (row) => row.revenue_share,
    render: (row) => formatShare(row.revenue_share),
    explain: (
      <Explain>
        <b>Выручка позиции ÷ выручка по всем отгрузкам</b> за выбранный период
        и выбранный канал.
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
 * Средней цены в итоге нет намеренно: среднее по разным товарам — число,
 * которое ничего не значит. Прочерк честнее.
 */
export function totalsFor(totals: ShipmentProducts["totals"]): Totals {
  return {
    label: `Итого за период · ${withPlural(totals.products_count, "наименование", "наименования", "наименований")}`,
    values: {
      quantity: formatQuantity(totals.quantity),
      free: formatQuantity(totals.free_quantity),
      revenue: formatMoney(totals.revenue_kopecks),
      avg: <span className="text-muted-foreground">—</span>,
      // Цена из карточки в итоге не суммируется по той же причине, что
      // и средняя: складывать цены разных товаров бессмысленно.
      card_price: <span className="text-muted-foreground">—</span>,
      // Доля приходит с сервера, а не пишется «100 %» жёстко. Без поиска
      // это ровно сто процентов; с поиском — сколько найденное занимает
      // в выручке выборки, и оно сходится со сложением колонки. Жёсткая
      // строка стояла бы над колонкой, где доли складываются в четырнадцать
      // процентов, и над пустой колонкой при нулевой выручке.
      share: formatShare(totals.revenue_share),
    },
  }
}
