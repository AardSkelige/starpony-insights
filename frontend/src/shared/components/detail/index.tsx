import { cn } from "@/shared/lib/utils"
import { Button } from "@/shared/ui/button"
import { Skeleton } from "@/shared/ui/skeleton"

/**
 * Кирпичи разбора строки: заголовок раздела, строка «подпись — значение»,
 * скелетон и сообщение о сбое.
 *
 * В `shared/`, потому что понадобились второй странице раздела и будут нужны
 * каждой следующей: разбор строки устроен одинаково везде — меняется только
 * то, что внутри.
 *
 * **Блок — карточка, а не абзац с подписью.** Раньше блоки отделялись только
 * заголовком капсом и волосяной линией на общем тонированном фоне, и пять
 * блоков подряд читались как один длинный список: границу между «Ценой»
 * и «Закупками» было видно, только если прочесть подпись. Карточка на той же
 * подложке читается как отдельный предмет, и взгляд делит разбор сам.
 *
 * **Ведущий блок выделен и стоит первым.** У каждой страницы есть блок,
 * ради которого строку и раскрывают: на «Материалах в приёмках» это запас
 * («пора ли закупать»), у «Поставщиков» — срок поставки. Он получает
 * заметную рамку, а когда данные требуют действия — ещё и цвет.
 * Цвет появляется только там, где есть о чём предупредить: рамка ради
 * порядка ничего не сообщает.
 */

/** Насколько всё плохо — тем же словарём, что у `core/services/coverage.py`. */
export type SectionTone = "default" | "warning" | "critical"

const TONES: Record<SectionTone, string> = {
  default: "border-border",
  warning:
    "border-warning/40 bg-[color-mix(in_oklab,var(--warning)_5%,var(--card))]",
  critical:
    "border-destructive/40 bg-[color-mix(in_oklab,var(--destructive)_5%,var(--card))]",
}

export function Section({
  title,
  note,
  explain,
  children,
  bare = false,
  lead = false,
  tone = "default",
}: {
  title: string
  /** Уточнение под заголовком: «показаны 20 из 59». */
  note?: string
  /**
   * Формула у заголовка раздела — как у колонки таблицы.
   *
   * Значок стоит рядом с подписью, а не отдельной строкой под блоком:
   * висящий сам по себе вопросительный знак не говорит, к чему относится,
   * и его просто не нажимают.
   */
  explain?: React.ReactNode
  children: React.ReactNode
  /**
   * За вкладкой заголовок лишний — его роль играет сама вкладка.
   *
   * Карточки там тоже нет: панель вкладки сама уже поверхность, и рамка
   * внутри неё была бы третьим уровнем вложенности подряд.
   */
  bare?: boolean
  /**
   * Ведущий блок страницы — тот, ради которого строку раскрывают.
   *
   * Один на страницу, и он же стоит первым. Выдели два — не выделено ничего.
   */
  lead?: boolean
  /**
   * Цвет предупреждения. Появляется только когда данные требуют действия:
   * «хватит на 0 дней» подсвечивается, «на 76» — нет. Рамка ради порядка
   * ничего не сообщает, а цветная рамка без повода обесценивает цветную
   * с поводом.
   */
  tone?: SectionTone
}) {
  return (
    <div
      className={cn(
        "min-w-0",
        !bare && "rounded-lg border bg-card p-3",
        !bare && lead && "shadow-xs",
        !bare && TONES[tone]
      )}
    >
      {/* Шапка одна на оба вида. `bare` снимает карточку, но не подпись:
          прежде за вкладкой заголовок выбрасывался, а значок объяснения
          оставался — и висел один, прижатый к правому краю, посреди пустой
          строки. Ровно то, что запрещает правило четырьмя абзацами выше:
          «висящий сам по себе вопросительный знак не говорит, к чему
          относится, и его просто не нажимают».

          Опасение, из-за которого подпись убирали, — что она повторит
          вкладку — не подтвердилось: за вкладкой «Цена» стоят блоки
          «Склад» и «Запас», и названия у них свои. */}
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs tracking-wide text-muted-foreground uppercase">
          {title}
        </span>
        {explain}
        <span className="h-px flex-1 bg-border" />
      </div>
      {note ? <p className="mb-1.5 text-xs text-muted-foreground">{note}</p> : null}
      {/* `contents` не добавляет уровень раскладки, но даёт общий паттерн:
          новый корень данных мягко проявляется на месте скелетона. */}
      <div className="motion-detail-content contents">{children}</div>
    </div>
  )
}

/** Список «подпись — значение». */
export function Facts({ children }: { children: React.ReactNode }) {
  return <dl className="flex flex-col">{children}</dl>
}

export function Fact({
  label,
  value,
}: {
  /**
   * Подпись. `ReactNode`, а не строка: рядом с ней встаёт значок объяснения
   * там, где само число расчётное, — «расход в день» надо объяснить так же,
   * как колонку таблицы.
   */
  label: React.ReactNode
  value: React.ReactNode
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b py-1.5 text-sm last:border-b-0">
      <dt className="min-w-0 text-muted-foreground">{label}</dt>
      {/* Число не ужимается и не переносится — уступает подпись.
          Иначе «231 530,38 ₽» ломается на две строки. */}
      <dd className="shrink-0 tabular-nums">{value}</dd>
    </div>
  )
}

/** Скелетон повторяет форму содержимого: строки той же высоты. */
export function Loading({ count }: { count: number }) {
  return (
    <div className="flex flex-col gap-2 py-1">
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton key={index} className="h-4 w-full" />
      ))}
    </div>
  )
}

/** Данные не доехали. Кнопка повтора обязательна: иначе тупик. */
export function Failed({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <span className="text-muted-foreground">Не удалось загрузить</span>
      <Button variant="outline" size="xs" onClick={onRetry}>
        Повторить
      </Button>
    </div>
  )
}
