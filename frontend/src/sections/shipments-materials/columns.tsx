import type {
  ShipmentMaterialRow,
  ShipmentMaterials,
} from "@/sections/shipments-materials/api"
import type { Column, Totals } from "@/shared/components/data-table"
import { Explain } from "@/shared/components/explain"
import {
  formatMoney,
  formatQuantity,
  formatShare,
  formatUnitPrice,
} from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Колонки таблицы «Материалы в отгрузках».
 *
 * Прочерк вместо нуля там, где цены нет вовсе: у 27 материалов из 161 её нет
 * в учёте — 24 этикетки приходят по нулю, три не закупались ни разу.
 * Ноль читался бы как «достался даром», а это разные вещи.
 */
export const COLUMNS: Column<ShipmentMaterialRow>[] = [
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
    label: "Израсходовано",
    numeric: true,
    sortKey: "quantity",
    changeValue: (row) => [row.quantity, row.uom],
    render: (row) => formatQuantity(row.quantity, row.uom),
    explain: (
      <Explain>
        <b>Сумма расхода по техкартам.</b> Каждое проданное изделие развёрнуто
        до сырья, полуфабрикаты раскрыты: закупают не «основу шампуня»,
        а воду и отдушку. Из каких изделий пришло — в раскрытии строки.
      </Explain>
    ),
  },
  {
    key: "price",
    label: "Цена закупки",
    numeric: true,
    // На узком экране прячется первой: цена важна, но она — слагаемое
    // стоимости, которая рядом, и её видно в раскрытии строки.
    hideOn: ["narrow"],
    changeValue: (row) => [row.price_kopecks, row.uom],
    render: (row) =>
      row.price_kopecks === null ? (
        <span className="text-muted-foreground">—</span>
      ) : (
        `${formatUnitPrice(row.price_kopecks)}/${row.uom || "ед."}`
      ),
    explain: (
      <Explain>
        Цена за единицу из <b>последней приёмки</b> этого материала — с номером
        документа и датой в раскрытии строки. Не из карточки товара: там она
        заполнена у 42 материалов из 161 и часто расходится с тем,
        что заплатили.
      </Explain>
    ),
  },
  {
    key: "cost",
    label: "Стоимость",
    numeric: true,
    sortKey: "cost",
    changeValue: (row) => row.cost_kopecks,
    render: (row) =>
      row.cost_kopecks === null ? (
        <span className="text-muted-foreground">—</span>
      ) : (
        formatMoney(row.cost_kopecks)
      ),
    explain: (
      <Explain>
        <b>Израсходовано × цена последней закупки.</b> Это стоимость замещения —
        во что обойдётся закупить столько же сегодня. Не себестоимость
        проданного: себестоимости на дату отгрузки в учёте нет, она появится
        в разделе «Прибыльность».
      </Explain>
    ),
  },
  {
    key: "share",
    label: "Доля",
    numeric: true,
    sortKey: "share",
    hideOn: ["narrow"],
    changeValue: (row) => row.cost_share,
    render: (row) => formatShare(row.cost_share),
    explain: (
      <Explain>
        <b>Стоимость материала ÷ стоимость всего сырья</b> за выбранный период
        и канал. Материалы без цены в знаменатель не входят.
      </Explain>
    ),
  },
  {
    key: "products",
    label: "Изделий",
    cardLabel: "Изделий-источников",
    numeric: true,
    sortKey: "products",
    hideOn: ["narrow"],
    changeValue: (row) => row.products_count,
    render: (row) => String(row.products_count),
    explain: (
      <Explain>
        Сколько разных проданных наименований потребовали этот материал.
        У воды их пятьдесят девять — она входит почти во всё.
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
 * итог не показывается. Лежат они рядом — расхождение видно глазом,
 * а тест `columns.test.ts` ловит его в любом случае.
 *
 * У расхода итога нет намеренно: сложить граммы со штуками нельзя,
 * а число под колонкой, где вперемешку то и другое, ничего не значит.
 */
export function totalsFor(totals: ShipmentMaterials["totals"]): Totals {
  return {
    label: `Итого · ${withPlural(totals.materials_count, "материал", "материала", "материалов")}`,
    values: {
      quantity: <span className="text-muted-foreground">разные единицы</span>,
      price: <span className="text-muted-foreground">—</span>,
      cost: formatMoney(totals.cost_kopecks),
      // Не жёсткое «100 %»: доли строк считаются от всей выборки, и при
      // поиске колонка складывается в восемь процентов, а не в сто.
      // Сервер отдаёт эту долю сам — фронт ничего не досчитывает.
      share: formatShare(totals.cost_share),
      products: <span className="text-muted-foreground">—</span>,
    },
  }
}
