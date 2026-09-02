import type { DeadlineRow } from "@/sections/deadlines/api"
import { formatMoney } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"
import { Card } from "@/shared/ui/card"

/**
 * Расчёты через площадку — отдельным блоком под таблицей.
 *
 * **Не строки таблицы и не спрятанный блок.** Товар ушёл, деньги не пришли —
 * значит показать обязаны. Но выплата площадки приходит реестром раз в цикл
 * и в учёт не заводится вовсе: у «Интернет Решений» ни одного платежа
 * на 236 235 ₽ отгрузок. Долгом это не является, и в итог дебиторки
 * не входит — иначе 176 360 ₽, по которым звонят, утонули бы в 437 514 ₽,
 * по которым не сделать ничего.
 *
 * **Признак берётся из учёта** — группа контрагента «маркетплейсы», которую
 * человек ведёт руками. Не флаг в нашей админке и не догадка по имени:
 * второй список тех же контрагентов разошёлся бы с первым.
 *
 * Открыт, а не свёрнут: в свёрнутом виде читался бы как необязательная
 * подробность, а это четверть всего отгруженного.
 */
export function Marketplaces({ rows }: { rows: DeadlineRow[] }) {
  if (rows.length === 0) {
    return null
  }

  const whole = rows.reduce((sum, row) => sum + row.debt_kopecks, 0)

  return (
    <Card className="gap-0 bg-muted py-0">
      <div className="flex flex-col gap-3 p-4">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-sm font-medium">
            Расчёты через площадку — {formatMoney(whole)}
          </span>
          <p className="text-xs text-muted-foreground">
            Отгружено и не закрыто, но выплата приходит реестром раз в цикл
            и в учёт не заводится. Долгом это не является — и в итог выше
            не входит.
          </p>
        </div>

        <dl className="flex flex-col">
          {rows.map((row) => (
            <div
              key={row.agent_id}
              className="flex items-baseline justify-between gap-3 border-b py-1.5 text-sm last:border-b-0"
            >
              <dt className="flex min-w-0 flex-col">
                <span className="truncate">{row.name}</span>
                <span className="text-xs text-muted-foreground">
                  {withPlural(row.documents_count, "документ", "документа", "документов")}
                  {" · до "}
                  {withPlural(row.oldest_age_days, "дня", "дней", "дней")}
                  {row.channels.length > 0 ? ` · ${row.channels.join(", ")}` : ""}
                </span>
              </dt>
              <dd className="shrink-0 tabular-nums">{formatMoney(row.debt_kopecks)}</dd>
            </div>
          ))}
        </dl>
      </div>
    </Card>
  )
}
