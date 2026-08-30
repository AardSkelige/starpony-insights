import { Download, RefreshCw } from "lucide-react"

import { useScreen } from "@/shared/hooks/use-screen"
import { formatSyncedAt } from "@/shared/lib/format"
import { cn } from "@/shared/lib/utils"
import { Button } from "@/shared/ui/button"
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
        <p
          className={cn(
            "mt-1 text-xs text-muted-foreground sm:hidden",
            refreshing && "motion-sync-pulse"
          )}
        >
          {refreshNote ?? formatSyncedAt(syncedAt)}
        </p>
      </div>

      <div className="flex items-center gap-2">
        <span
          className={cn(
            "hidden text-xs text-muted-foreground sm:inline",
            refreshing && "motion-sync-pulse"
          )}
        >
          {refreshNote ?? formatSyncedAt(syncedAt)}
        </span>

        {onExport ? (
          <HeaderAction
            icon={Download}
            label="Экспорт"
            onClick={onExport}
            busy={exporting}
            busyMotion="pulse"
            hint="Выгрузит то, что сейчас на экране, — с учётом фильтров и сортировки. Формат XLSX."
          />
        ) : null}

        {onRefresh ? (
          <HeaderAction
            icon={RefreshCw}
            label={refreshing ? "Обновляем…" : "Обновить"}
            onClick={onRefresh}
            busy={refreshing}
            busyMotion="spin"
            hint="Перетянет данные из МойСклада прямо сейчас, не дожидаясь ночного расписания. Занимает около двадцати секунд. Чаще раза в три минуты запускать нельзя: лимит запросов общий с ботом, который проверяет учёт круглосуточно."
          />
        ) : null}

      </div>
    </div>
  )
}

/**
 * Действие в шапке: кнопка с подписью на большом экране, иконка на телефоне.
 *
 * Два разных рендера, а не один с погашенной подписью. Погасить не выходит:
 * вариант `sm` объявляет `has-data-[icon=inline-start]:pl-1.5`, и этот отступ
 * перебивает `px-0` снаружи — селектор с `:has()` специфичнее обычного класса.
 * Плюс `gap-1` продолжает отделять иконку от спрятанного текста. Кнопка
 * получалась не квадратной, а вытянутой, с иконкой, сдвинутой влево.
 *
 * Это тот же случай, что с `SelectTrigger` и `Separator` из §15: подгонять
 * чужой компонент снаружи бесполезно, надо посмотреть, **чем** он рисует
 * то, что вы меняете, и повторить этот способ. Здесь способ — вариант
 * `size="icon"`, который для того и существует.
 */
const BUSY_MOTION = {
  spin: "motion-refresh-spin",
  pulse: "motion-sync-pulse",
} as const

function HeaderAction({
  icon: Icon,
  label,
  onClick,
  busy,
  busyMotion,
  hint,
}: {
  icon: typeof Download
  label: string
  onClick: () => void
  busy: boolean
  /**
   * Занятость показывает сама иконка, а не подмена её на кружок: подмена
   * меняет форму, и это читается как мигание рядом со второй такой же кнопкой.
   *
   * Движение разное, потому что разные и процессы: обновление ходит в МойСклад
   * двадцать секунд по кругу — это `spin`; выгрузка отдаёт файл один раз
   * и ждать её нечего — это `pulse`.
   */
  busyMotion: "spin" | "pulse"
  hint: string
}) {
  const screen = useScreen()

  if (screen === "phone") {
    return (
      <Button
        variant="outline"
        size="icon"
        onClick={onClick}
        disabled={busy}
        // Подпись уходит в `aria-label`: без неё кнопка немая для экранного
        // диктора, а подсказка по наведению на телефоне не показывается.
        aria-label={label}
        // 40 точек — минимум под палец (§15), у варианта `icon` их 32.
        className="size-10"
      >
        <Icon className={cn(busy && BUSY_MOTION[busyMotion])} />
      </Button>
    )
  }

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button variant="outline" size="sm" onClick={onClick} disabled={busy}>
            <Icon
              data-icon="inline-start"
              className={cn(busy && BUSY_MOTION[busyMotion])}
            />
            {label}
          </Button>
        }
      />
      {/* Снизу, а не сверху. Кнопки стоят в самой шапке страницы, и подсказка
          над ними накрывает заголовок раздела и отметку «данные на 14:32» —
          то есть закрывает контекст ровно в тот момент, когда его читают. */}
      <TooltipContent side="bottom">{hint}</TooltipContent>
    </Tooltip>
  )
}
