import type { ChannelRow, Channels } from "@/sections/channels/api"
import { slotColor } from "@/sections/channels/api"
import { ReceiptCell } from "@/sections/channels/ui/receipt-cell"
import type { Column, Totals } from "@/shared/components/data-table"
import { Explain } from "@/shared/components/explain"
import { formatDate, formatMoney, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Колонки таблицы «Каналы продаж».
 *
 * **Главный вопрос страницы читается из двух соседних колонок.** Озон даёт
 * 135 отгрузок из 305 и 17 % выручки, «Точка продаж» — 34 отгрузки и 37 %.
 * Одно слово «канал» описывает вал мелких заказов и редкие крупные, и рядом
 * стоящие «Выручка» и «Отгрузок» отвечают на это без единого расчёта:
 * сортировка по разным колонкам показывает разных «лучших».
 *
 * **Покупатели — не украшение.** У Озона, Яндекса и ХорсСмарта контрагент
 * ровно один: это площадка, а не люди. У «ВКонтакте» их 33. Число отвечает
 * на «канал приводит клиентов или это одна витрина», и без него «Точка
 * продаж» с восемью покупателями выглядит так же, как маркетплейс.
 */
export const COLUMNS: Column<ChannelRow>[] = [
  {
    key: "name",
    label: "Канал",
    sortKey: "name",
    changeValue: (row) => [row.name, row.shipments_count],
    render: (row) => (
      <span className="flex min-w-0 items-center gap-2">
        {/* Метка цвета — та же, что у канала в графиках выше. Без неё
            столбик в стопке приходится опознавать по легенде, отдельно
            от строки, про которую и открыли страницу. */}
        <span
          aria-hidden
          className="size-2 shrink-0 rounded-[2px]"
          style={{ background: slotColor(row.slot) }}
        />
        <span className="flex min-w-0 flex-col">
          <span className="truncate max-sm:font-medium">{row.name}</span>
          {/* Подзаголовок только на телефоне: там «Отгрузок» и «Покупателей»
              скрыты, чтобы на экран помещались четыре карточки, а не две
              с половиной. Числа при этом нужны — они и есть вопрос страницы. */}
          <span className="hidden text-xs text-muted-foreground max-sm:block">
            {withPlural(row.shipments_count, "отгрузка", "отгрузки", "отгрузок")} ·{" "}
            {withPlural(row.buyers_count, "покупатель", "покупателя", "покупателей")}
          </span>
        </span>
      </span>
    ),
  },
  {
    key: "revenue",
    label: "Выручка",
    numeric: true,
    strong: true,
    sortKey: "revenue",
    changeValue: (row) => row.revenue_kopecks,
    render: (row) => formatMoney(row.revenue_kopecks),
    explain: (
      <Explain>
        Сумма отгрузок канала за период — как в документах, до копейки.
        Берётся из <b>самого документа</b>, а не складывается из строк: сумма
        документа остаётся фактом учёта даже тогда, когда синхронизация
        пропустит позицию.
      </Explain>
    ),
  },
  {
    key: "share",
    label: "Доля",
    numeric: true,
    hideOn: ["narrow"],
    changeValue: (row) => row.revenue_share,
    render: (row) => formatShare(row.revenue_share),
    explain: (
      <Explain>
        Сколько выручки приносит канал от <b>всей выборки</b>. Период
        в знаменатель входит, поиск — нет: набрав «озон», человек сужает
        список строк, а не то, что продали.
      </Explain>
    ),
  },
  {
    key: "shipments",
    label: "Отгрузок",
    numeric: true,
    sortKey: "shipments",
    changeValue: (row) => [row.shipments_count, row.receipt.free_shipments],
    render: (row) => (
      <span className="flex flex-col items-end">
        <span>{row.shipments_count}</span>
        {/* Подстрочник появляется только когда есть что сказать. У Озона
            и Яндекса даром не уходило ничего, и строка «135 · 0 даром»
            была бы шумом. */}
        {row.receipt.free_shipments > 0 ? (
          <span className="text-xs text-muted-foreground">
            {row.receipt.free_shipments} даром
          </span>
        ) : null}
      </span>
    ),
    explain: (
      <Explain>
        Сколько раз через канал что-то отгружали. <b>С выручкой расходится
        в разы:</b> Озон даёт 44 % отгрузок и 17 % денег. Подстрочником —
        отгрузки с нулевой суммой: подарки, образцы и призы. Товар по ним
        со склада ушёл, денег не принёс.
      </Explain>
    ),
  },
  {
    key: "receipt",
    label: "Средний чек",
    numeric: true,
    sortKey: "receipt",
    changeValue: (row) => row.receipt,
    render: (row) => <ReceiptCell receipt={row.receipt} />,
    explain: (
      <Explain>
        <b>Медиана суммы отгрузки.</b> Не среднее: у «Точки продаж» одна
        отгрузка на 99 495 ₽ поднимает среднее с 2 772 до 13 766 ₽ — впятеро.
        Отрезок под числом — от нуля до самой крупной отгрузки канала, метка
        на нём — медиана. <b>Ноль — это ответ:</b> у Instagram и Telegram
        больше половины отгрузок ушли даром, и чека у канала действительно нет.
      </Explain>
    ),
  },
  {
    key: "buyers",
    label: "Покупателей",
    numeric: true,
    sortKey: "buyers",
    hideOn: ["narrow", "phone"],
    changeValue: (row) => row.buyers_count,
    render: (row) => row.buyers_count,
    explain: (
      <Explain>
        Сколько разных контрагентов покупало через канал. <b>Единица — это
        площадка, а не человек:</b> у Озона, Яндекса и ХорсСмарта контрагент
        один на все отгрузки. В итоге под таблицей покупатели{" "}
        <b>объединяются, а не складываются</b>: один и тот же приходит через
        несколько каналов и был бы посчитан дважды.
      </Explain>
    ),
  },
  {
    key: "products",
    label: "Товаров",
    numeric: true,
    sortKey: "products",
    hideOn: ["narrow", "phone"],
    changeValue: (row) => row.products_count,
    render: (row) => row.products_count,
    explain: (
      <Explain>
        Сколько разных наименований уходит через канал — насколько он широкий.
        Считается по строкам отгрузок, поэтому объединяется в итоге так же,
        как покупатели: один товар продаётся через несколько каналов.
      </Explain>
    ),
  },
  {
    key: "last",
    label: "Последняя",
    numeric: true,
    sortKey: "last",
    // Уходит с узкого экрана и телефона: там остаются четыре числа, ради
    // которых страницу открывают. Дата видна в разборе строки — и она
    // единственная колонка, по которой заглохший канал виден без открытия:
    // Telegram молчит с 27 июля.
    hideOn: ["narrow", "phone"],
    changeValue: (row) => row.last_moment,
    render: (row) => formatDate(row.last_moment),
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
 * **У чека итога нет намеренно.** Медианы не складываются и не усредняются:
 * «средний чек по всем каналам» — число, по которому нельзя принять ни
 * одного решения, потому что продают всегда через какой-то один.
 */
export function totalsFor(totals: Channels["totals"]): Totals {
  return {
    label: `Итого · ${withPlural(totals.channels_count, "канал", "канала", "каналов")}`,
    values: {
      revenue: formatMoney(totals.revenue_kopecks),
      share: formatShare(totals.revenue_share),
      shipments: totals.shipments_count,
      receipt: <span className="text-muted-foreground">—</span>,
      // Объединение, а не сложение: один покупатель приходит через
      // несколько каналов, один товар продаётся через несколько.
      buyers: totals.buyers_count,
      products: totals.products_count,
    },
  }
}
