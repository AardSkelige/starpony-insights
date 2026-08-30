import * as React from "react"
import { Radio } from "lucide-react"

import { exportUrl, useShipmentMaterials } from "@/sections/shipments-materials/api"
import { COLUMNS, SORT_KEYS, totalsFor } from "@/sections/shipments-materials/columns"
import { Coverage } from "@/sections/shipments-materials/ui/coverage"
import { RowDetail } from "@/sections/shipments-materials/ui/row-detail"
import { refreshNote, useRefresh, useSyncStatus } from "@/shared/api/sync"
import { DataTable } from "@/shared/components/data-table"
import { DetailDrawer } from "@/shared/components/detail-drawer"
import { FiltersBar } from "@/shared/components/filters/bar"
import { Page } from "@/shared/components/page"
import { PageHeader } from "@/shared/components/page-header"
import { TableFooter } from "@/shared/components/table-footer"
import { useScreen } from "@/shared/hooks/use-screen"
import { useTableParams } from "@/shared/hooks/use-table-params"
import { withPlural } from "@/shared/lib/plural"

const SEARCH_PLACEHOLDER = "Материал, артикул или код"
const SEARCH_LABEL = "Поиск по материалам"

export function ShipmentMaterialsPage() {
  const screen = useScreen()
  // Минус обязателен: «cost» значит «по возрастанию», и страница открывалась бы
  // с этикеток по копейке вместо сырья, ради которого её открыли.
  const table = useTableParams({
    defaultSort: "-cost",
    sortKeys: SORT_KEYS,
    pickerKey: "channel",
  })

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const query = useShipmentMaterials({
    ...table.applied,
    page: table.page,
    ordering: table.ordering,
    pageSize: table.pageSize,
  })
  const data = query.data

  // Только идентификатор: снимок строки после «Обновить» показывал бы
  // старые числа рядом со свежим разбором.
  const [pickedId, setPickedId] = React.useState<number | null>(null)

  const rows = data?.results ?? []
  const picked = rows.find((row) => row.material_id === pickedId) ?? null
  const pageCount = data ? Math.max(1, Math.ceil(data.count / table.pageSize)) : 1

  return (
    <Page>
      <PageHeader
        title="Материалы в отгрузках"
        subtitle="Сколько сырья ушло вместе с проданной продукцией"
        syncedAt={data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || sync.running}
        refreshNote={refreshNote(refresh, sync.running)}
        onExport={() => {
          window.location.assign(
            exportUrl({ ...table.applied, ordering: table.ordering })
          )
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
        searchPlaceholder={SEARCH_PLACEHOLDER}
        searchLabel={SEARCH_LABEL}
      />

      <DataTable
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.material_id}
        loading={query.isPending}
        // Приглушаются только устаревшие данные — те, что показаны, пока
        // едут новые после смены фильтра или страницы.
        refreshing={query.isPlaceholderData}
        // Тот же признак, что у кнопки и отметки свежести: чужой прогон
        // виден всем, и его результат подсвечивается так же, как свой.
        syncPending={refresh.isPending || sync.running}
        syncFailed={refresh.isError}
        dataVersion={query.dataUpdatedAt}
        error={query.isError}
        onRetry={() => query.refetch()}
        emptyTitle={
          table.activeCount > 0
            ? "Под эти фильтры сырьё не попало"
            : "За этот период сырьё не расходовалось"
        }
        emptyHint={
          table.activeCount > 0
            ? "Попробуйте расширить период, снять фильтр по каналу или изменить запрос."
            : "Сырьё считается по техкартам проданной продукции. Данные появятся после первой синхронизации с МойСкладом."
        }
        renderDetail={(row) => <RowDetail row={row} query={table.applied} />}
        expandedKey={table.expanded}
        onToggle={(row) =>
          table.setExpanded((current) =>
            current === row.material_id ? null : row.material_id
          )
        }
        onOpen={(row) => setPickedId(row.material_id)}
        totals={data ? totalsFor(data.totals) : undefined}
        sort={table.sort}
        onSort={table.changeSort}
      />

      {data && (rows.length > 0 || table.page > 1) ? (
        <TableFooter
          // Только материалы: число это про показанные строки и сходится
          // с поиском. Отгрузки из `coverage` описывают выборку целиком,
          // и рядом с найденными материалами читались бы как их отгрузки —
          // «22 материала · 294 отгрузки». Число отгрузок стоит в сводке
          // под таблицей, где оно про всю выборку и это верно.
          summary={withPlural(data.count, "материал", "материала", "материалов")}
          page={table.page}
          pageCount={pageCount}
          pageSize={table.pageSize}
          onPage={table.setPage}
          onPageSize={table.setPageSize}
        />
      ) : null}

      {/* Сводка и охват — под таблицей и свёрнуты: главное на странице
          строки, а эти числа отвечают на вопрос «полное ли оно»,
          который задают реже. */}
      {data ? (
        <Coverage coverage={data.coverage} withoutPlan={data.without_plan} />
      ) : null}

      {/* Разбор — для узкого экрана и телефона. На широком он раскрывается
          прямо в строке.

          Числа самой строки в панели повторяются (`repeatRowNumbers`):
          строка закрыта затемнением, свериться с ней нельзя. */}
      {screen !== "wide" ? (
        <DetailDrawer
          open={picked !== null}
          title={picked?.name ?? ""}
          subtitle={
            picked
              ? [picked.code, picked.article, picked.uom].filter(Boolean).join(" · ")
              : undefined
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
