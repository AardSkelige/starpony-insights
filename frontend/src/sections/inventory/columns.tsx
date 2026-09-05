import type { Inventory, InventoryRow } from "@/sections/inventory/api"
import type { Column, Totals } from "@/shared/components/data-table"
import { Explain } from "@/shared/components/explain"
import { formatDate, formatMoney, formatQuantity } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Колонки таблицы «Инвентаризация».
 *
 * Строка — позиция номенклатуры, а не документ: список из шести
 * инвентаризаций человек и так видит в учёте, а вопрос, на который учёт
 * не отвечает, — что не пересчитывали вовсе. Таких позиций 239 из 312.
 *
 * Числа последнего пересчёта, а не суммы по всем: «числилось 42, нашли 5» —
 * факт одного дня, и сложение таких пар дало бы величину, которой
 * не было ни в одном документе.
 */

/** «Никогда» — это ответ, а не пробел, и выглядеть должно ответом.
 *
 * Разметкой, а не компонентом: файл колонок экспортирует список, а не
 * компоненты, и объявление компонента рядом ломает горячую перезагрузку. */
const NEVER = <span className="font-medium text-warning">никогда</span>
const DASH = <span className="text-muted-foreground">—</span>

/** Расхождение со знаком: плюс — излишек, минус — недостача. */
function correctionOf(value: string, uom: string): string {
  const number = Number(value)
  return `${number > 0 ? "+" : ""}${formatQuantity(value, uom)}`
}

export const COLUMNS: Column<InventoryRow>[] = [
  {
    key: "name",
    label: "Позиция",
    sortKey: "name",
    changeValue: (row) => [row.name, row.folder, row.counted_times],
    render: (row) => (
      <span className="flex min-w-0 flex-col">
        {/* Переносится, а не обрезается: «Картонный короб 42,5х16,5х19см
            (Короб «PROБизнес»)» после обрезки не отличается от соседнего
            короба — а их в номенклатуре два десятка, и различаются они
            ровно концом названия. */}
        <span className="line-clamp-2 whitespace-normal max-sm:line-clamp-none max-sm:font-medium">
          {row.name}
        </span>
        {/* Папка — на узком экране и телефоне, где своей колонки у неё нет.
            Без неё «Короб №198» и «Отдушка Зелёный чай» стоят рядом
            без единого признака, чем они друг от друга отличаются. */}
        {/* Папка — подстрочником, а не своей колонкой: она забирала
            четверть ширины таблицы, и «Расхождение» с «В деньгах»
            уезжали за правый край экрана (`DESIGN.md` §15). */}
        <span className="text-xs text-muted-foreground">
          {row.folder || "Без папки"}
        </span>
      </span>
    ),
  },
  {
    key: "last",
    label: "Считали",
    sortKey: "last",
    changeValue: (row) => [row.last_moment, row.last_store],
    render: (row) =>
      row.last_moment ? (
        <span className="flex flex-col">
          <span>{formatDate(row.last_moment)}</span>
          {/* Склад обязателен: их три, пересчёт трогает один, и дата без
              склада читается как «посчитали весь товар». */}
          <span className="text-xs text-muted-foreground">{row.last_store}</span>
        </span>
      ) : (
        NEVER
      ),
  },
  {
    key: "days_ago",
    label: "Дней назад",
    numeric: true,
    sortKey: "last",
    hideOn: ["narrow", "phone"],
    changeValue: (row) => row.days_ago,
    render: (row) => (row.days_ago === null ? DASH : row.days_ago),
  },
  {
    key: "calculated",
    label: "Числилось",
    numeric: true,
    hideOn: ["narrow", "phone"],
    changeValue: (row) => row.calculated,
    render: (row) =>
      row.calculated === null ? DASH : formatQuantity(row.calculated, row.uom),
  },
  {
    key: "counted",
    label: "Нашли",
    numeric: true,
    hideOn: ["narrow", "phone"],
    changeValue: (row) => row.counted,
    render: (row) =>
      row.counted === null ? DASH : formatQuantity(row.counted, row.uom),
  },
  {
    key: "correction",
    label: "Расхождение",
    numeric: true,
    sortKey: "correction",
    changeValue: (row) => [row.correction, row.diverged_times],
    render: (row) => {
      if (row.correction === null) return DASH
      const number = Number(row.correction)
      if (number === 0) return <span className="text-muted-foreground">сошлось</span>
      return (
        <span className="flex flex-col items-end">
          <span className={number < 0 ? "text-destructive" : "text-success"}>
            {correctionOf(row.correction, row.uom)}
          </span>
          {/* Повтор важнее размера: разошлось дважды из двух — это не
              случайность счёта, а место, где учёт систематически расходится
              с полкой. */}
          {row.diverged_times > 1 ? (
            <span className="text-xs text-muted-foreground">
              {row.diverged_times}-й раз
            </span>
          ) : null}
        </span>
      )
    },
  },
  {
    key: "money",
    label: "В деньгах",
    numeric: true,
    sortKey: "money",
    changeValue: (row) => row.correction_money_kopecks,
    render: (row) =>
      row.correction_money_kopecks === null ? (
        <span className="text-muted-foreground">
          {row.correction === null || Number(row.correction) === 0
            ? "—"
            : "не оценено"}
        </span>
      ) : (
        <span
          className={
            row.correction_money_kopecks < 0 ? "text-destructive" : "text-success"
          }
        >
          {formatMoney(row.correction_money_kopecks)}
        </span>
      ),
    explain: (
      <Explain>
        <b>Расхождение × себестоимость единицы на сегодня.</b> В самих
        документах инвентаризации цена заполнена у меньшинства позиций,
        и учёт показывает по остальным 0 ₽ при живой недостаче. Поэтому
        считаем сами — и с карточкой документа это число не сойдётся:
        себестоимость берётся сегодняшняя, а пересчёты были раньше.
        «Не оценено» — себестоимости нет вовсе.
      </Explain>
    ),
  },
]

/**
 * По чему таблица умеет сортировать — выводится из самих колонок.
 *
 * Второй список разъехался бы с первым: колонку добавляют, а ключ забывают,
 * и ссылка с новым порядком приходит к экрану ошибки вместо таблицы.
 */
export const SORT_KEYS: readonly string[] = Array.from(
  new Set(COLUMNS.flatMap((column) => (column.sortKey ? [column.sortKey] : [])))
)

/**
 * Итог по всей выборке, а не по видимой странице.
 *
 * Живёт рядом с колонками: подвал задаётся их ключами, и опечатка даёт
 * пустую ячейку молча.
 *
 * **Ни у «числилось», ни у «нашли», ни у «расхождения» итога нет.** Это
 * количества в разных единицах — граммы спирта и штуки коробов, — и сложить
 * их нельзя. Число разошедшихся позиций стояло было под колонкой
 * «Расхождение» и читалось как «45 штук»: под колонкой обязано стоять то же,
 * что в её ячейках, иначе итог спорит со столбцом, оставаясь верным сам
 * по себе. Теперь оно в подписи, где рядом со словом «разошлось» ни с чем
 * не путается.
 */
export function totalsFor(totals: Inventory["totals"]): Totals {
  return {
    label: `Итого · ${withPlural(totals.products_count, "позиция", "позиции", "позиций")} · разошлось ${totals.diverged_count}`,
    values: {
      last: (
        <span className="text-warning">
          не считали {totals.never_counted_count}
        </span>
      ),
      money: (
        <span className="flex flex-col items-end">
          <span>{formatMoney(totals.money_kopecks)}</span>
          {/* Итог без этого числа выглядел бы полным: у части расхождений
              себестоимости нет, и в сумму они не вошли вовсе. */}
          {totals.unpriced_count > 0 ? (
            <span className="text-xs font-normal text-muted-foreground">
              не оценено {totals.unpriced_count}
            </span>
          ) : null}
        </span>
      ),
    },
  }
}
