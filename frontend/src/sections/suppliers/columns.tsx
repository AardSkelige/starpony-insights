import type { SupplierRow, Suppliers } from "@/sections/suppliers/api"
import { SpanCell } from "@/sections/suppliers/ui/span"
import type { Column, Totals } from "@/shared/components/data-table"
import { Explain } from "@/shared/components/explain"
import { formatDate, formatMoney, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Колонки таблицы «Поставщики».
 *
 * Восемь колонок. Две из них — расчётные, и обе медианы: как часто возит
 * и сколько ждать после заказа. Каждая идёт со шкалой разброса, потому что
 * одно число здесь врёт: у «Ревады-Невы» срок 21 день сложился из 2 и 40,
 * у «Спецума» интервал 68 — из 2 и 134.
 *
 * Прочерк вместо нуля у регулярности: у семи поставщиков из двадцати трёх
 * поставка была одна, и промежутка между поставками не существует.
 * **А вот у срока ноль — это ответ:** у «Принтеца», «Интернет Решений»
 * и «ИП Белых» медиана ровно ноль, у них забирают, а не ждут доставку,
 * и это половина всех закупок.
 */
export const COLUMNS: Column<SupplierRow>[] = [
  {
    key: "name",
    label: "Поставщик",
    sortKey: "name",
    changeValue: (row) => [
      row.name,
      row.supplies_count,
      row.materials_count,
    ],
    render: (row) => (
      <span className="flex min-w-0 flex-col">
        {/* Название переносится в две строки, а не обрезается: «ООО "Аптечный
            склад Химфармпродукт"» — 35 знаков, и обрезанное после «Аптечный
            скла…» оно не отличается от соседа. Самое длинное в учёте —
            «ИП Николаева Анастасия Васильевна». */}
        <span className="line-clamp-2 whitespace-normal max-sm:line-clamp-none max-sm:font-medium">
          {row.name}
        </span>
        {/* Подзаголовок только на телефоне: там «Поставок» и «Наименований»
            скрыты, чтобы на экран помещались четыре карточки, а не две
            с половиной. Числа при этом нужны — они отвечают, насколько
            поставщик значим, — и переезжают сюда. */}
        <span className="hidden text-xs text-muted-foreground max-sm:block">
          {withPlural(row.supplies_count, "поставка", "поставки", "поставок")} ·{" "}
          {withPlural(
            row.materials_count,
            "наименование",
            "наименования",
            "наименований"
          )}
        </span>
      </span>
    ),
  },
  {
    key: "supplies",
    label: "Поставок",
    numeric: true,
    sortKey: "supplies",
    // Уходит везде, кроме широкого экрана. Колонка первого ряда важности —
    // «сколько денег» и обе медианы; «Поставок» их поддерживает, а места
    // занимает столько же. Отдав его, имя поставщика перестаёт обрезаться:
    // «ООО "АПТЕЧНЫ…» не отличить от «ООО "АПТЕКА…». Само число есть
    // в подзаголовке карточки на телефоне и в разборе строки.
    hideOn: ["narrow", "phone"],
    changeValue: (row) => [row.supplies_count, row.delivery_days],
    render: (row) => (
      <span className="flex flex-col items-end">
        <span>{row.supplies_count}</span>
        {/* Подстрочник появляется только когда есть что сказать: приёмок
            больше, чем дней поставок. Таких поставщиков четыре из двадцати
            трёх, и у остальных строка «14 · 14 дней» была бы шумом. */}
        {row.delivery_days < row.supplies_count ? (
          <span className="text-xs text-muted-foreground">
            {withPlural(row.delivery_days, "день", "дня", "дней")}
          </span>
        ) : null}
      </span>
    ),
    explain: (
      <Explain>
        Приёмок за период. Подстрочником — <b>дней поставок</b>: три приёмки
        одним днём это одна поставка, разбитая на бумаги. У «Интернет Решений»
        31 марта их три. Промежутки между поставками считаются по дням,
        иначе появились бы интервалы в ноль дней — цикл, которого не было.
      </Explain>
    ),
  },
  {
    key: "amount",
    label: "Сумма",
    numeric: true,
    strong: true,
    sortKey: "amount",
    changeValue: (row) => row.amount_kopecks,
    render: (row) => formatMoney(row.amount_kopecks),
  },
  {
    key: "share",
    label: "Доля",
    numeric: true,
    hideOn: ["narrow"],
    changeValue: (row) => row.amount_share,
    render: (row) => formatShare(row.amount_share),
    explain: (
      <Explain>
        Сколько закупок у этого поставщика от <b>всей выборки</b>. Период
        в знаменатель входит, поиск — нет: набрав «принт», человек сужает
        список строк, а не то, что закупили.
      </Explain>
    ),
  },
  {
    key: "materials",
    label: "Наимен.",
    cardLabel: "Наименований",
    numeric: true,
    sortKey: "materials",
    hideOn: ["narrow", "phone"],
    changeValue: (row) => row.materials_count,
    render: (row) => row.materials_count,
    explain: (
      <Explain>
        Сколько разных наименований приходит от этого поставщика — насколько
        он незаменим. В итоге под таблицей они <b>объединяются, а не
        складываются</b>: 21 материал из 212 приходит больше чем от одного
        поставщика, и сложение колонки посчитало бы его дважды.
      </Explain>
    ),
  },
  {
    key: "regularity",
    label: "Возит раз в",
    numeric: true,
    sortKey: "regularity",
    changeValue: (row) => row.regularity,
    render: (row) => (
      <SpanCell span={row.regularity} emptyLabel="поставка одна" />
    ),
    explain: (
      <Explain>
        <b>Медиана промежутка между днями поставок.</b> Не среднее: у
        «Полицвета» один разрыв в 73 дня даёт среднее 22,5 дня против медианы
        6,5 — вчетверо. Отрезок под числом — от самого короткого промежутка
        до самого длинного, метка на нём — медиана. Прочерк там, где поставка
        была одна: у семи поставщиков из двадцати трёх.
      </Explain>
    ),
  },
  {
    key: "lead_time",
    label: "Срок поставки",
    numeric: true,
    sortKey: "lead_time",
    changeValue: (row) => row.lead_time,
    render: (row) => (
      <SpanCell
        span={row.lead_time}
        zeroLabel="в тот же день"
        emptyLabel="заказ не найден"
      />
    ),
    explain: (
      <Explain>
        <b>Медиана дней от заказа поставщику до приёмки.</b> Ноль — это ответ,
        а не пробел: у «Принтеца» и «Интернет Решений» товар забирают,
        а не ждут доставку, и таких закупок половина. Связь «заказ → приёмка»
        в учёте заполнена у всех 95 приёмок.
      </Explain>
    ),
  },
  {
    key: "last",
    label: "Последняя",
    numeric: true,
    sortKey: "last",
    // На телефоне карточка оставляет четыре числа, ради которых экран
    // и открывают: сумма, доля и обе медианы. Дата последней поставки —
    // в разборе, блок «Что берём».
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
 * У обеих медиан итога нет намеренно: средняя из медиан не значит ничего,
 * а «срок поставки по всем поставщикам» — это число, по которому нельзя
 * принять ни одного решения, потому что заказывают всегда у кого-то одного.
 */
export function totalsFor(totals: Suppliers["totals"]): Totals {
  return {
    label: `Итого · ${withPlural(totals.suppliers_count, "поставщик", "поставщика", "поставщиков")}`,
    values: {
      supplies: totals.supplies_count,
      amount: formatMoney(totals.amount_kopecks),
      share: formatShare(totals.amount_share),
      // Объединение, а не сложение: 21 материал приходит от двоих и больше.
      materials: totals.materials_count,
      regularity: <span className="text-muted-foreground">—</span>,
      lead_time: <span className="text-muted-foreground">—</span>,
    },
  }
}
