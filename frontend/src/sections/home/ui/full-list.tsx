import * as React from "react"

import type { HomeListRow } from "@/sections/home/api"
import { formatEstimate } from "@/sections/home/format"
import { SidePanel } from "@/sections/home/ui/side-panel"
import { Button } from "@/shared/ui/button"

/**
 * «Что за эти 173 позиции» — список целиком, панелью.
 *
 * **Панель, а не переход в раздел.** Правило `PRD.md` §5.1 требует, чтобы
 * нажатие вело в раздел с уже наложенным фильтром, — но фильтра «лежит
 * без движения» нет ни на одной странице проекта, и отбор там другой:
 * «Материалы в приёмках» показывают закупленное за период, а не то, что
 * стоит на складе без расхода. Ссылка туда открывала бы страницу, где
 * этих ста семидесяти трёх строк не найти, — то есть обещала бы ответ
 * и не давала его. Владелец на это и указал.
 *
 * Пока такого разреза нет, честнее показать список там, где задан вопрос.
 * Заведём страницу — ссылка встанет на место панели.
 */
export function FullList({
  label,
  title,
  subtitle,
  rows,
  total,
}: {
  /** Подпись кнопки: «Показать все 173». */
  label: string
  title: string
  subtitle: string
  rows: HomeListRow[]
  /** Сколько всего — чтобы честно сказать, что список подрезан. */
  total: number
}) {
  const [open, setOpen] = React.useState(false)

  if (!rows.length) return null

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        {label}
      </Button>
      <SidePanel
        open={open}
        title={title}
        subtitle={subtitle}
        onClose={() => setOpen(false)}
      >
        <div className="flex flex-col">
          {rows.map((row) => (
            <div
              key={row.name}
              className="flex items-baseline justify-between gap-4 border-b py-2 last:border-b-0"
            >
              <div className="min-w-0">
                {/* Название переносится, а не обрезается: позиции различаются
                    концом — «…Кокосовое молоко» и «…Голубая орхидея». */}
                <div className="text-sm">{row.name}</div>
                <div className="text-xs text-muted-foreground">{row.note}</div>
              </div>
              <div className="shrink-0 text-sm tabular-nums">
                {formatEstimate(row.value)}
              </div>
            </div>
          ))}
          {total > rows.length ? (
            // Подрезку называем: молча показанные пятьдесят из ста семидесяти
            // трёх читаются как весь список, и сумма в плитке перестаёт
            // сходиться с тем, что видно.
            <p className="pt-3 text-xs text-muted-foreground">
              Показаны {rows.length} крупнейших из {total}. Остальные — мелочь,
              на решение не влияющая.
            </p>
          ) : null}
        </div>
      </SidePanel>
    </>
  )
}
