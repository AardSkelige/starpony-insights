import type { Profitability, ProfitabilityRow } from "@/sections/profitability/api"
import { MarketplaceMark, ProfitCell } from "@/sections/profitability/ui/cells"
import type { Column, Totals } from "@/shared/components/data-table"
import { Explain } from "@/shared/components/explain"
import { formatMoney, formatQuantity, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Колонки таблицы «Прибыльность».
 *
 * Шесть колонок, и главная из них — прибыль: страница отвечает на «на чём
 * зарабатываем», а не «сколько продали». Под числом прибыли — полоса: длина
 * отвечает на «на чём держится заработок» за секунду, тогда как столбец
 * семизначных чисел приходится сравнивать глазами (`PRD.md` §8.0).
 *
 * **Колонки доли нет намеренно.** Её работу делает та же полоса, а две шкалы
 * одного и того же в одной строке спорят между собой. Доля при этом
 * приходит с сервера и живёт в подсказке полосы: точное число нужно редко.
 */
export const COLUMNS: Column<ProfitabilityRow>[] = [
  {
    key: "name",
    label: "Товар",
    sortKey: "name",
    changeValue: (row) => [row.name, row.profit_kopecks, row.quantity],
    render: (row) => (
      <span className="flex min-w-0 flex-col">
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {/* Имя переносится, а не обрезается: пять кондиционеров различаются
              концом названия, и после обрезки становятся неотличимы. */}
          <span className="line-clamp-2 whitespace-normal max-sm:line-clamp-none max-sm:font-medium">
            {row.name}
          </span>
          {Number(row.marketplace_quantity) > 0 ? (
            <MarketplaceMark share={marketplaceShare(row)} />
          ) : null}
        </span>
        <span className="font-mono text-xs text-muted-foreground">{row.article}</span>
      </span>
    ),
  },
  {
    key: "quantity",
    label: "Продано",
    numeric: true,
    sortKey: "quantity",
    changeValue: (row) => [row.quantity, row.free_quantity],
    render: (row) => (
      <span className="flex flex-col items-end max-sm:items-start">
        <span>{formatQuantity(row.quantity, row.uom)}</span>
        {/* Отданное даром — рядом со штуками, а не в отдельной колонке:
            «продано 270» и «отгружено 375» иначе выглядят расхождением. */}
        {Number(row.free_quantity) > 0 ? (
          <span className="text-xs text-muted-foreground">
            +{formatQuantity(row.free_quantity)} даром
          </span>
        ) : null}
      </span>
    ),
  },
  {
    key: "revenue",
    label: "Выручка",
    numeric: true,
    sortKey: "revenue",
    hideOn: ["narrow"],
    changeValue: (row) => row.revenue_kopecks,
    render: (row) => formatMoney(row.revenue_kopecks),
    explain: (
      <Explain>
        Сумма отгрузок за период. <b>Товар, ушедший по договору комиссии,
        входит сюда только после отчёта комиссионера</b> — до него он лежит
        на реализации и деньгами ещё не стал. Поэтому выручка здесь меньше,
        чем в «Товарах в отгрузках»; разница видна в блоке «Полнота расчёта».
      </Explain>
    ),
  },
  {
    key: "cost",
    label: "Себестоимость",
    numeric: true,
    sortKey: "cost",
    hideOn: ["narrow", "phone"],
    changeValue: (row) => row.cost_kopecks,
    render: (row) =>
      row.cost_kopecks === null ? (
        // Прочерк, а не ноль: ноль читался бы как «достался даром».
        <span className="text-muted-foreground">—</span>
      ) : (
        formatMoney(row.cost_kopecks)
      ),
    explain: (
      <Explain>
        Во сколько нам обошлось проданное — <b>по цене на момент продажи</b>,
        а не сегодняшней. Считает МойСклад методом ФИФО, мы забираем готовым.
        При выключенных подарках берётся доля платных штук: у подарка
        себестоимость настоящая, а выручки нет вовсе. Прочерк означает
        «в отчёте её нет», а не «ноль».
      </Explain>
    ),
  },
  {
    key: "profit",
    label: "Прибыль",
    numeric: true,
    strong: true,
    sortKey: "profit",
    changeValue: (row) => row.profit_kopecks,
    render: (row) => <ProfitCell row={row} />,
    explain: (
      <Explain>
        Выручка минус себестоимость проданного. <b>Комиссия площадок сюда
        не входит</b> — Озон, Яндекс.Маркет и ПМТ удерживают её при выплате,
        и отдельным документом в учёте её нет. По строкам со значком
        «площадка» прибыль поэтому завышена. Накладные расходы и доставка
        тоже не вычтены: это валовая прибыль, а не чистая.
      </Explain>
    ),
  },
  {
    key: "margin",
    label: "Маржа",
    numeric: true,
    sortKey: "margin",
    changeValue: (row) => row.margin,
    render: (row) => formatShare(row.margin),
    explain: (
      <Explain>
        Какую часть выручки составляет прибыль. Отвечает на «сколько
        остаётся с рубля»: две позиции с одинаковой прибылью могут иметь
        разную маржу, и дешевле в производстве та, у которой она выше.
        Прочерк — себестоимости в отчёте нет, и делить не на что.
      </Explain>
    ),
  },
]

/**
 * Какая часть выручки строки прошла через площадку.
 *
 * `null` — выручки нет вовсе: товар ушёл только даром, и делить не на что.
 * Ноль здесь означал бы «через площадку не продавали», а это другое.
 */
function marketplaceShare(row: ProfitabilityRow): number | null {
  if (row.revenue_kopecks <= 0) return null
  return row.marketplace_revenue_kopecks / row.revenue_kopecks
}

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
 * Живёт рядом с колонками: подвал задаётся **их ключами**, и опечатка
 * в ключе даёт пустую ячейку молча.
 */
export function totalsFor(totals: Profitability["totals"]): Totals {
  return {
    label: `Итого · ${withPlural(totals.products_count, "товар", "товара", "товаров")}`,
    values: {
      quantity: formatQuantity(totals.quantity),
      revenue: formatMoney(totals.revenue_kopecks),
      cost: formatMoney(totals.cost_kopecks),
      profit: formatMoney(totals.profit_kopecks),
      margin: formatShare(totals.margin),
    },
  }
}
