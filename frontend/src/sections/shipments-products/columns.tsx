import { Explain } from "@/shared/components/explain"
import type { Column } from "@/shared/components/data-table"
import type { ShipmentProductRow } from "@/sections/shipments-products/api"
import {
  formatMoney,
  formatQuantity,
  formatShare,
  formatUnitPrice,
} from "@/shared/lib/format"

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
    render: (row) => (
      <span className="flex min-w-0 flex-col">
        <span className="truncate">{row.name}</span>
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
    render: (row) =>
      Number(row.free_quantity) > 0 ? formatQuantity(row.free_quantity) : "—",
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
    key: "share",
    label: "Доля в выручке",
    cardLabel: "Доля",
    numeric: true,
    sortKey: "share",
    hideOn: ["narrow"],
    render: (row) => formatShare(row.revenue_share),
    explain: (
      <Explain>
        <b>Выручка позиции ÷ выручка по всем отгрузкам</b> за выбранный период
        и выбранный канал.
      </Explain>
    ),
  },
]
