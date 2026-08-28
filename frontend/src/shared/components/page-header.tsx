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
    // На телефоне кнопки сжаты до иконок и стоят рядом с названием: нажимают
    // их заметно реже, чем ищут, а всю ширину они занимали как раз у поиска.
    <div className="flex flex-wrap items-start gap-3 sm:gap-x-4">
      <div className="min-w-0 flex-1">
        <h1 className="text-xl font-semibold tracking-tight sm:truncate">{title}</h1>
        {subtitle ? (
          <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
        <p className="mt-1 text-xs text-muted-foreground sm:hidden">
          {refreshNote ?? formatSyncedAt(syncedAt)}
        </p>
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
                  // На телефоне — квадрат 40×40 без подписи: под палец
                  // попадает так же, а места занимает вчетверо меньше.
                  className="max-sm:size-10 max-sm:px-0"
                >
                  {exporting ? <Spinner data-icon="inline-start" /> : <Download data-icon="inline-start" />}
                  {/* Подпись не удаляется, а прячется: экранному диктору
                      она нужна, а `aria-label` дублировал бы её третьей копией. */}
                  <span className="max-sm:sr-only">Экспорт</span>
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
                  className="max-sm:size-10 max-sm:px-0"
                >
                  {refreshing ? <Spinner data-icon="inline-start" /> : <RefreshCw data-icon="inline-start" />}
                  <span className="max-sm:sr-only">
                    {refreshing ? "Обновляем…" : "Обновить"}
                  </span>
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
