import { cn } from "@/shared/lib/utils"

/**
 * Состав величины: одна полоса из двух частей.
 *
 * Отвечает на «из чего сложилось» — форма для доли целого, а не для
 * сравнения категорий: отношение читается длиной, без деления в уме.
 *
 * Ровно две части. Третья превратила бы полосу в столбчатую диаграмму,
 * читаемую по площади, а у неё другие правила — и другая форма.
 *
 * Зазор между сегментами в 2 точки обязателен: без него две заливки
 * сливаются в одну и граница между ними теряется на глаз.
 */

/** Ниже этой доли подпись внутрь сегмента не помещается — уходит под полосу. */
const FITS = 27

export function Split({
  left,
  right,
  caption,
  emphasis = "right",
}: {
  left: { label: string; value: number; tone?: "muted" | "warning" }
  right: { label: string; value: number }
  caption?: React.ReactNode
  /**
   * Какая часть главная — её сегмент рисуется плотным тоном.
   *
   * По умолчанию правая: в «сложилось из себестоимости и прибыли» главная
   * прибыль, и она стоит второй. Но в «продано и лежит на реализации»
   * главное — проданное, а оно первое, и без переключателя выходило,
   * что взгляд ведёт к меньшему и второстепенному числу.
   */
  emphasis?: "left" | "right"
}) {
  const total = left.value + right.value
  if (total <= 0) return null

  const share = (left.value / total) * 100

  /**
   * Подписи внутри сегментов или под полосой.
   *
   * Внутри они читаются лучше — число стоит на своей части, и связывать
   * их взглядом не нужно. Но узкий сегмент обрезает подпись **посреди
   * слова и без многоточия**: в разборе строки «На реализации · 27 050 ₽»
   * превращалось в «На реализации ·». Найдено снимком панели на 900 точках.
   */
  const inside = share >= FITS && 100 - share >= FITS

  const leftFill =
    left.tone === "warning"
      ? "bg-warning"
      : emphasis === "left"
        ? "bg-primary"
        : "bg-primary/20"
  const rightFill = emphasis === "left" ? "bg-primary/20" : "bg-primary"

  return (
    <div className="flex flex-col gap-2">
      <div className={cn("flex gap-0.5", inside ? "h-7" : "h-2")}>
        <div
          className={cn(
            "flex items-center overflow-hidden rounded-l px-2 text-xs font-medium whitespace-nowrap",
            leftFill,
            left.tone === "warning"
              ? "text-background"
              : emphasis === "left"
                ? "text-primary-foreground"
                : "text-foreground"
          )}
          style={{ width: `${share}%` }}
        >
          {inside ? left.label : null}
        </div>
        <div
          className={cn(
            "flex items-center overflow-hidden rounded-r px-2 text-xs font-medium whitespace-nowrap",
            rightFill,
            emphasis === "left" ? "text-foreground" : "text-primary-foreground"
          )}
          style={{ width: `${100 - share}%` }}
        >
          {inside ? right.label : null}
        </div>
      </div>

      {inside ? null : (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          <Legend fill={leftFill} label={left.label} />
          <Legend fill={rightFill} label={right.label} />
        </div>
      )}

      {caption ? (
        <p className="text-xs text-muted-foreground">{caption}</p>
      ) : null}
    </div>
  )
}

function Legend({ fill, label }: { fill: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden className={cn("size-2 shrink-0 rounded-[2px]", fill)} />
      {label}
    </span>
  )
}
