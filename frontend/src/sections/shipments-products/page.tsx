import * as React from "react"
import { Radio } from "lucide-react"

import { exportUrl, useShipmentProducts } from "@/sections/shipments-products/api"
import { COLUMNS, SORT_KEYS, totalsFor } from "@/sections/shipments-products/columns"
import { Coverage } from "@/sections/shipments-products/ui/coverage"
import { RowDetail } from "@/sections/shipments-products/ui/row-detail"
import { DataTable } from "@/shared/components/data-table"
import { DetailDrawer } from "@/shared/components/detail-drawer"
import { FiltersBar } from "@/shared/components/filters/bar"
import { ConsignmentNote } from "@/shared/components/consignment"
import { Page } from "@/shared/components/page"
import { PageHeader } from "@/shared/components/page-header"
import { refreshNote, useRefresh, useSyncStatus } from "@/shared/api/sync"
import { TableFooter } from "@/shared/components/table-footer"
import { useScreen } from "@/shared/hooks/use-screen"
import { useTableParams } from "@/shared/hooks/use-table-params"
import { withPlural } from "@/shared/lib/plural"

export function ShipmentProductsPage() {
  const screen = useScreen()
  // Минус обязателен: «revenue» значит «по возрастанию», и страница
  // открывалась бы с позиций, не принесших ничего.
  const table = useTableParams({
    defaultSort: "-revenue",
    sortKeys: SORT_KEYS,
    pickerKey: "channel",
  })

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const query = useShipmentProducts({
    ...table.applied,
    page: table.page,
    ordering: table.ordering,
    pageSize: table.pageSize,
  })
  const data = query.data

  // Только идентификатор: снимок строки после «Обновить» показывал бы
  // старые числа рядом со свежей разбивкой по каналам.
  const [pickedId, setPickedId] = React.useState<number | null>(null)

  const rows = data?.results ?? []
  const picked = rows.find((row) => row.product_id === pickedId) ?? null
  const pageCount = data ? Math.max(1, Math.ceil(data.count / table.pageSize)) : 1

  return (
    <Page>
      <PageHeader
        title="Товары в отгрузках"
        subtitle="Что и сколько продано за период"
        syncedAt={data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || sync.running}
        refreshNote={refreshNote(refresh, sync.running)}
        onExport={() => {
          window.location.assign(exportUrl({ ...table.applied, ordering: table.ordering }))
        }}
      />

      <FiltersBar
        value={table.filters}
        onChange={table.changeFilters}
        onReset={table.resetFilters}
        picker={{
          key: "channel",
          label: "Канал",
          icon: Radio,
          options: data?.channels ?? [],
        }}
        searchPlaceholder="Название, артикул или код"
        searchLabel="Поиск по товарам"
      />

      {/* Единственное предупреждение страницы, которое не свёрнуто: без него
          выручка читается как заработанная, а треть её — товар, отгруженный
          на реализацию. Считается по показанному и сужается фильтрами
          вместе со строками. */}
      {data ? <ConsignmentNote share={data.totals.consignment} /> : null}

      <DataTable
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.product_id}
        loading={query.isPending}
        // Приглушаются только устаревшие данные — те, что показаны, пока
        // едут новые после смены фильтра или страницы. Любая загрузка
        // подряд не годится: React Query перечитывает данные при возврате
        // на вкладку, и таблица темнела каждый раз, когда человек
        // переключался в другое окно и обратно, хотя числа не менялись.
        refreshing={query.isPlaceholderData}
        // Тот же признак, что у кнопки и отметки свежести: чужой прогон
        // виден всем, и его результат подсвечивается так же, как свой.
        syncPending={refresh.isPending || sync.running}
        syncFailed={refresh.isError}
        dataVersion={query.dataUpdatedAt}
        error={query.isError}
        onRetry={() => query.refetch()}
        emptyTitle="За этот период ничего не продано"
        emptyHint={
          table.activeCount > 0
            ? "Попробуйте расширить период или снять фильтр по каналу."
            : "Данные появятся после первой синхронизации с МойСкладом."
        }
        renderDetail={(row) => <RowDetail row={row} query={table.applied} />}
        expandedKey={table.expanded}
        onToggle={(row) =>
          table.setExpanded((current) =>
            current === row.product_id ? null : row.product_id
          )
        }
        onOpen={(row) => setPickedId(row.product_id)}
        totals={data ? totalsFor(data.totals) : undefined}
        sort={table.sort}
        onSort={table.changeSort}
      />

      {data && (rows.length > 0 || table.page > 1) ? (
        <TableFooter
          summary={`${withPlural(data.count, "наименование", "наименования", "наименований")} · ${withPlural(data.totals.documents_count, "отгрузка", "отгрузки", "отгрузок")}`}
          page={table.page}
          pageCount={pageCount}
          pageSize={table.pageSize}
          onPage={table.setPage}
          onPageSize={table.setPageSize}
        />
      ) : null}

      {/* Сводка — под таблицей и свёрнута, как на пяти соседних страницах:
          они обязаны открываться одинаково. Числа здесь про выборку целиком,
          а подвал считает показанное — поэтому блоки и разные. */}
      {data ? <Coverage coverage={data.coverage} /> : null}

      {/* Панель деталей — для узкого экрана и телефона. На широком те же
          детали раскрываются прямо в строке.

          Числа самой строки в панели повторяются (`repeatRowNumbers`):
          строка закрыта затемнением, свериться с ней нельзя. */}
      {screen !== "wide" ? (
        <DetailDrawer
          open={picked !== null}
          title={picked?.name ?? ""}
          subtitle={
            picked ? [picked.code, picked.article].filter(Boolean).join(" · ") : undefined
          }
          onClose={() => setPickedId(null)}
        >
          {picked ? (
            <RowDetail
              row={picked}
              query={table.applied}
              repeatRowNumbers
              tabbed={screen === "phone"}
            />
          ) : null}
        </DetailDrawer>
      ) : null}
    </Page>
  )
}
