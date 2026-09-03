/**
 * Одно число в свёрнутой сводке под таблицей.
 *
 * Подпись, само число, пояснение под ним и значок формулы рядом с подписью.
 * **Значок обязателен у расчётного числа** (`CLAUDE.md` §4): без источника
 * оно остаётся числом, за которое никто не отвечает.
 *
 * В `shared/`, потому что копий было пять — по одной у «Каналов продаж»,
 * «Сроков оплаты», «Поставщиков» и обеих страниц материалов, — и они уже
 * начали расходиться: у «Сроков оплаты» появился приглушённый вид, у
 * остальных четырёх нет. Шестая копия понадобилась «Товарам в отгрузках»,
 * и вместо неё заведено одно место.
 */
export function SummaryStat({
  label,
  value,
  note,
  explain,
  quiet = false,
}: {
  label: string
  value: string
  note: string
  explain: React.ReactNode
  /**
   * Число приглушено: оно рядом с главными, но складывать его с ними нельзя.
   * У «Сроков оплаты» так набраны деньги площадок и товар на реализации —
   * это не долг, и в один ряд с дебиторкой их ставить нельзя, иначе глаз
   * сложит все три.
   */
  quiet?: boolean
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {/* Подпись ужимается, значок объяснения — нет: без него расчётное
            число остаётся числом без источника. */}
        <span className="min-w-0 truncate">{label}</span>
        {explain}
      </div>
      <div
        className={
          quiet
            ? "text-lg font-medium tracking-tight text-muted-foreground tabular-nums"
            : "text-lg font-semibold tracking-tight tabular-nums"
        }
      >
        {value}
      </div>
      <div className="text-xs text-muted-foreground">{note}</div>
    </div>
  )
}
