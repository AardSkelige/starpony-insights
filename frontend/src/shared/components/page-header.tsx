import { Download, RefreshCw } from "lucide-react"

import { formatSyncedAt } from "@/shared/lib/format"
import { Button } from "@/shared/ui/button"
import { Spinner } from "@/shared/ui/spinner"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

type Props = {
  title: string
  subtitle?: string
  /** Момент последней успешной синхронизации. `null` — её ещё не было. */
  syncedAt: string | null
  onRefresh?: () => void
  refreshing?: boolean
  /**
   * Что вышло из последнего нажатия «Обновить».
   *
   * Показывать это обязательно: прогон почти всегда заканчивается теми же
   * числами на экране, и без ответа кнопка выглядит сломанной.
   */
  refreshNote?: string | null
  onExport?: () => void
  exporting?: boolean
}

/**
 * Шапка раздела: название, отметка свежести и две кнопки.
 *
 * Кнопки рисует сама шапка, а не страница: собранные вручную, они на десяти
 * разделах разъедутся и подписями, и порядком. Отметка «данные на 14:32» —
 * часть шапки, а не опция: без неё человек не отличит свежие числа от
 * вчерашних, а именно на них он принимает решение.
 */
export function PageHeader({
  title,
  subtitle,
  syncedAt,
  onRefresh,
  refreshing = false,
  refreshNote,
  onExport,
  exporting = false,
}: Props) {
  return (
    <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? (
          <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>

      <div className="flex items-center gap-2">
        <span className="hidden text-xs text-muted-foreground sm:inline">
          {refreshNote ?? formatSyncedAt(syncedAt)}
        </span>

        {onExport ? (
          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onExport}
                  disabled={exporting}
                >
                  {exporting ? <Spinner data-icon="inline-start" /> : <Download data-icon="inline-start" />}
                  Экспорт
                </Button>
              }
            />
            <TooltipContent>
              Выгрузит то, что сейчас на экране, — с учётом фильтров и сортировки.
              Формат XLSX.
            </TooltipContent>
          </Tooltip>
        ) : null}

        {onRefresh ? (
          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onRefresh}
                  disabled={refreshing}
                >
                  {refreshing ? <Spinner data-icon="inline-start" /> : <RefreshCw data-icon="inline-start" />}
                  {refreshing ? "Обновляем…" : "Обновить"}
                </Button>
              }
            />
            <TooltipContent>
              Перетянет данные из МойСклада прямо сейчас, не дожидаясь ночного
              расписания. Занимает около двадцати секунд. Чаще раза в три
              минуты запускать нельзя: лимит запросов общий с ботом,
              который проверяет учёт круглосуточно.
            </TooltipContent>
          </Tooltip>
        ) : null}
      </div>
    </div>
  )
}
