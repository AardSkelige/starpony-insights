import * as React from "react"

import { exportUrl, useSuppliers } from "@/sections/suppliers/api"
import { COLUMNS, SORT_KEYS, totalsFor } from "@/sections/suppliers/columns"
import { Coverage } from "@/sections/suppliers/ui/coverage"
import { RowDetail } from "@/sections/suppliers/ui/row-detail"
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

const SEARCH_PLACEHOLDER = "Название поставщика"
const SEARCH_LABEL = "Поиск по поставщикам"

export function SuppliersPage() {
  const screen = useScreen()
  // Минус обязателен: «amount» значит «по возрастанию», и страница
  // открывалась бы с тех, у кого закупили на 720 ₽, вместо тех,
  // на кого ушла треть денег.
  const table = useTableParams({
    defaultSort: "-amount",
    sortKeys: SORT_KEYS,
    // Справочника у этой страницы нет: поставщик и есть строка таблицы.
    // Выбери его фильтром — в таблице останется одна строка, а переключиться
    // будет нечем, кроме сброса.
  })

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const query = useSuppliers({
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
  const picked = rows.find((row) => row.supplier_id === pickedId) ?? null
  const pageCount = data ? Math.max(1, Math.ceil(data.count / table.pageSize)) : 1

  return (
    <Page>
      <PageHeader
        title="Поставщики"
        subtitle="Кто, на сколько и как часто поставляет"
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
        searchPlaceholder={SEARCH_PLACEHOLDER}
        searchLabel={SEARCH_LABEL}
      />

      <DataTable
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.supplier_id}
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
            ? "Под эти фильтры поставщики не попали"
            : "За этот период ничего не закупали"
        }
        emptyHint={
          table.activeCount > 0
            ? "Попробуйте расширить период или изменить запрос."
            : "Поставщики берутся из приёмок МойСклада. Данные появятся после первой синхронизации."
        }
        renderDetail={(row) => <RowDetail row={row} />}
        expandedKey={table.expanded}
        onToggle={(row) =>
          table.setExpanded((current) =>
            current === row.supplier_id ? null : row.supplier_id
          )
        }
        onOpen={(row) => setPickedId(row.supplier_id)}
        totals={data ? totalsFor(data.totals) : undefined}
        sort={table.sort}
        onSort={table.changeSort}
      />

      {data && (rows.length > 0 || table.page > 1) ? (
        <TableFooter
          // Оба числа — про показанные строки. Приёмки из `coverage`
          // описывают выборку целиком, и при поиске подвал читался бы как
          // «2 поставщика · 95 приёмок», где 95 относятся ко всем 23.
          summary={`${withPlural(data.count, "поставщик", "поставщика", "поставщиков")} · ${withPlural(data.totals.supplies_count, "приёмка", "приёмки", "приёмок")}`}
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

          `inDrawer` отвечает за два следствия сразу: числа самой строки
          повторяются (строка закрыта затемнением, свериться с ней нельзя)
          и разбор не добавляет свой отступ — панель даёт собственный. */}
      {screen !== "wide" ? (
        <DetailDrawer
          open={picked !== null}
          title={picked?.name ?? ""}
          subtitle={
            picked
              ? `${withPlural(picked.supplies_count, "поставка", "поставки", "поставок")} · ${withPlural(picked.materials_count, "наименование", "наименования", "наименований")}`
              : undefined
          }
          onClose={() => setPickedId(null)}
        >
          {picked ? (
            <RowDetail row={picked} inDrawer />
          ) : null}
        </DetailDrawer>
      ) : null}
    </Page>
  )
}
