import * as React from "react"
import { Building2 } from "lucide-react"

import { exportUrl, useSupplyMaterials } from "@/sections/supplies-materials/api"
import { COLUMNS, SORT_KEYS, totalsFor } from "@/sections/supplies-materials/columns"
import { Coverage } from "@/sections/supplies-materials/ui/coverage"
import { RowDetail } from "@/sections/supplies-materials/ui/row-detail"
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

export function SupplyMaterialsPage() {
  const screen = useScreen()
  // Минус обязателен: «amount» значит «по возрастанию», и страница
  // открывалась бы с этикеток по копейке вместо того, на что ушли деньги.
  const table = useTableParams({
    defaultSort: "-amount",
    sortKeys: SORT_KEYS,
    // Своё у этой страницы: у приёмки канала продаж не существует —
    // товар приходит от контрагента, а не через Озон.
    pickerKey: "supplier",
  })

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const query = useSupplyMaterials({
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
        title="Материалы в приёмках"
        subtitle="Что и почём закупали за период"
        syncedAt={data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || sync.running}
        refreshNote={refreshNote(refresh, sync.running, sync)}
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
          key: "supplier",
          label: "Поставщик",
          icon: Building2,
          options: data?.suppliers ?? [],
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
            ? "Под эти фильтры закупки не попали"
            : "За этот период ничего не закупали"
        }
        emptyHint={
          table.activeCount > 0
            ? "Попробуйте расширить период, снять фильтр по поставщику или изменить запрос."
            : "Закупки берутся из приёмок МойСклада. Данные появятся после первой синхронизации."
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
          // Оба числа — про показанные строки. Приёмки из `coverage`
          // описывают выборку целиком, и при поиске подвал читался бы как
          // «22 материала · 93 приёмки», где 93 относятся ко всем 212.
          summary={`${withPlural(data.count, "материал", "материала", "материалов")} · ${withPlural(data.totals.documents_count, "приёмка", "приёмки", "приёмок")}`}
          page={table.page}
          pageCount={pageCount}
          pageSize={table.pageSize}
          onPage={table.setPage}
          onPageSize={table.setPageSize}
        />
      ) : null}

      {/* Сводка — под таблицей и свёрнута, как на соседних страницах:
          главное здесь строки, а эти числа отвечают на вопрос
          «полное ли оно», который задают реже. */}
      {data ? <Coverage coverage={data.coverage} /> : null}

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
