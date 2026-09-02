import type { UseQueryResult } from "@tanstack/react-query"

import type { DeadlineDetail, DeadlineRow } from "@/sections/deadlines/api"
import { Fact, Facts, Loading, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatDate, formatMoney } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"
import { cn } from "@/shared/lib/utils"

type Detail = UseQueryResult<DeadlineDetail>

/**
 * Неоплаченные документы контрагента — ведущий блок разбора.
 *
 * Ради него строку и раскрывают: «нам должны 98 125 ₽» не даёт повода
 * для разговора, а «отчёт 00012 от 27 августа на 81 160 ₽ не оплачен вовсе,
 * а по 00008 недоплачено 16 965 ₽» — даёт.
 *
 * От свежих к старым: разбор читают сверху, и первым вопросом идёт
 * «что последнее ушло без оплаты».
 */
export function Documents({
  detail,
  row,
  repeatRowNumbers = false,
}: {
  detail: Detail
  row: DeadlineRow
  repeatRowNumbers?: boolean
}) {
  const data = detail.data

  return (
    <Section
      title="Неоплаченные документы"
      lead
      note={note(data)}
      explain={
        <Explain>
          Сумма документа минус оплаченное. Срок оплаты считается как{" "}
          <b>дата документа плюс дни отсрочки</b> — из карточки контрагента
          или из самого документа, если там задан индивидуальный срок.
          Отсрочки нет ни у кого, поэтому в колонке срока стоит прочерк:
          посчитать его не из чего.
        </Explain>
      }
    >
      {repeatRowNumbers ? (
        <Facts>
          <Fact label="Долг" value={formatMoney(row.debt_kopecks)} />
          <Fact
            label="Старейший"
            value={withPlural(row.oldest_age_days, "день", "дня", "дней")}
          />
        </Facts>
      ) : null}

      {detail.isPending ? <Loading count={4} /> : null}

      {data ? (
        <>
          {/* Таблица, а не список фактов: у документа пять величин, и класть
              их парами «подпись — значение» значило бы двадцать строк там,
              где четыре. Прокрутка своя — на телефоне колонок больше,
              чем помещается. */}
          <div className="-mx-1 overflow-x-auto px-1">
            {/* Минимальная ширина обязательна: без неё `w-full` ужимает
                таблицу под экран телефона вместо прокрутки — название
                документа рассыпается по слову на строку.
                На телефоне при этом «Сумма» и «Оплачено» уходят: долг это
                их разность, формула — в подсказке блока, а прокручивать
                до главного числа человек не станет. */}
            <table className="w-full min-w-[21rem] text-sm sm:min-w-[36rem]">
              <thead>
                <tr className="text-xs text-muted-foreground">
                  <th className="py-1.5 pr-3 text-left font-medium">Документ</th>
                  <th className="py-1.5 pr-3 text-right font-medium">Возраст</th>
                  <th className="py-1.5 pr-3 text-right font-medium max-sm:hidden">
                    Сумма
                  </th>
                  <th className="py-1.5 pr-3 text-right font-medium max-sm:hidden">
                    Оплачено
                  </th>
                  <th className="py-1.5 pr-3 text-right font-medium">Долг</th>
                  <th className="py-1.5 text-right font-medium">Срок оплаты</th>
                </tr>
              </thead>
              <tbody>
                {data.documents.map((document) => (
                  <tr key={`${document.kind}-${document.number}`} className="border-t">
                    <td className="py-1.5 pr-3 whitespace-normal">
                      <span className="font-medium">{document.number}</span>
                      <span className="block text-xs text-muted-foreground">
                        {formatDate(document.moment)} · {document.kind_label}
                        {document.channel ? ` · ${document.channel}` : ""}
                      </span>
                      {/* Комментарий из учёта: причина живёт в нём, а не
                          в справочнике категорий, которого нет. */}
                      {document.description ? (
                        <span className="block text-xs text-muted-foreground">
                          {document.description}
                        </span>
                      ) : null}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">
                      {withPlural(document.age_days, "день", "дня", "дней")}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums max-sm:hidden">
                      {formatMoney(document.total_kopecks)}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums text-muted-foreground max-sm:hidden">
                      {formatMoney(document.paid_kopecks)}
                    </td>
                    <td className="py-1.5 pr-3 text-right font-medium tabular-nums">
                      {formatMoney(document.debt_kopecks)}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">
                      <Due document={document} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Хвост сворачивается, но не выбрасывается: без него показанные
              слагаемые перестают сходиться с суммой строки. */}
          {data.rest_count > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Ещё {withPlural(data.rest_count, "документ", "документа", "документов")} на{" "}
              {formatMoney(data.rest_debt_kopecks)} — показаны самые свежие.
              Все до одного есть в выгрузке.
            </p>
          ) : null}

          {/* Одно объяснение на все прочерки, а не по строке у каждого:
              причина у них общая — отсрочки нет. Показывается только когда
              прочерки действительно есть; заполнят отсрочку хотя бы части
              документов — у тех появится дата, а фраза останется про
              оставшиеся. */}
          {undated(data) > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              {undated(data) === data.documents.length
                ? "Срок оплаты не посчитан ни у одного документа: отсрочка не указана ни у контрагента, ни в самих документах."
                : `Срок не посчитан у ${withPlural(undated(data), "документа", "документов", "документов")}: отсрочка у них не указана.`}
            </p>
          ) : null}
        </>
      ) : null}
    </Section>
  )
}

/**
 * Срок оплаты документа — дата плюс то, сколько до неё осталось.
 *
 * Прочерк, а не пустота: отсутствие срока — это состояние учёта («отсрочка
 * не задана»), и пустая ячейка читалась бы как недогрузившееся число.
 *
 * **Цвет только там, где есть о чём предупредить.** Просрочено — `destructive`,
 * срок на подходе — `warning`, всё остальное обычным текстом: цветная строка
 * без повода обесценивает цветную с поводом. И цвет здесь никогда не один:
 * рядом всегда написано словами, на сколько просрочено, — статусу нельзя
 * держаться на цвете, его не все различают.
 */
function Due({ document }: { document: DeadlineDetail["documents"][number] }) {
  if (document.due_date === null) {
    return <span className="text-muted-foreground">—</span>
  }

  const left = document.days_left
  const overdue = document.group === "overdue"
  const soon = document.group === "soon"

  return (
    <span className="flex flex-col items-end">
      <span
        className={cn(
          overdue && "font-medium text-destructive",
          soon && "font-medium text-warning"
        )}
      >
        {formatDate(document.due_date)}
      </span>
      {left !== null ? (
        <span
          className={cn(
            "text-xs",
            overdue ? "text-destructive" : soon ? "text-warning" : "text-muted-foreground"
          )}
        >
          {left < 0
            ? `просрочен на ${withPlural(-left, "день", "дня", "дней")}`
            : left === 0
              ? "сегодня"
              : `через ${withPlural(left, "день", "дня", "дней")}`}
        </span>
      ) : null}
    </span>
  )
}

/** Сколько показанных документов остались без срока оплаты. */
function undated(data: DeadlineDetail): number {
  return data.documents.filter((document) => document.due_date === null).length
}

function note(data: DeadlineDetail | undefined): string | undefined {
  if (!data || data.rest_count === 0) {
    return undefined
  }
  return `показаны ${data.documents.length} из ${data.documents_count}`
}
