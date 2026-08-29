import { Button } from "@/shared/ui/button"
import { Skeleton } from "@/shared/ui/skeleton"

/**
 * Кирпичи разбора строки: заголовок раздела, строка «подпись — значение»,
 * скелетон и сообщение о сбое.
 *
 * В `shared/`, потому что понадобились второй странице раздела и будут нужны
 * каждой следующей: разбор строки устроен одинаково везде — меняется только
 * то, что внутри.
 */

export function Section({
  title,
  note,
  explain,
  children,
  bare = false,
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
  /** За вкладкой заголовок лишний — его роль играет сама вкладка. */
  bare?: boolean
}) {
  return (
    <div className="min-w-0">
      {bare ? (
        // За вкладкой заголовок лишний — его роль играет сама вкладка,
        // но значок объяснения обязан остаться: на телефоне подсказки
        // у колонок таблицы недостижимы вовсе (таблица там карточками),
        // и это единственное место, где формулу можно посмотреть.
        explain ? <div className="mb-2 flex justify-end">{explain}</div> : null
      ) : (
        <div className="mb-2 flex items-center gap-2">
          <span className="text-xs tracking-wide text-muted-foreground uppercase">
            {title}
          </span>
          {explain}
          <span className="h-px flex-1 bg-border" />
        </div>
      )}
      {note ? <p className="mb-1.5 text-xs text-muted-foreground">{note}</p> : null}
      {children}
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
