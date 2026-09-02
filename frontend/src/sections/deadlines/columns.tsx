import type { DeadlineRow, Deadlines } from "@/sections/deadlines/api"
import type { Column, Totals } from "@/shared/components/data-table"
import { Explain } from "@/shared/components/explain"
import { formatMoney, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Колонки таблицы «Сроки оплаты».
 *
 * Пять колонок, и последняя — не срок, а **возраст**. Дата оплаты в учёте
 * не хранится, она считается: «дата документа плюс дни отсрочки». Отсрочка
 * не проставлена ни у одного из 107 контрагентов, поэтому срока сегодня нет
 * ни у одного документа, а возраст есть у каждого.
 *
 * Колонка «Просрочено» стоит рядом с возрастом и сегодня **пуста у всех
 * строк** — отсрочки нет ни у кого, и сказать «нарушен срок» не о чем.
 * Прочерк здесь честнее нуля: ноль читался бы как «всё в порядке», а на деле
 * «мы не знаем». Заполнят отсрочку — колонка оживёт сама.
 *
 * Возраст она при этом не заменяет и не дублирует: возраст говорит «висит
 * давно», просрочка — «нарушен договор». Это разные утверждения, и второе
 * появляется только там, где договорённость записана в учёте.
 */
export const COLUMNS: Column<DeadlineRow>[] = [
  {
    key: "name",
    label: "Контрагент",
    sortKey: "name",
    changeValue: (row) => [row.name, row.debt_kopecks, row.documents_count],
    render: (row) => (
      <span className="flex min-w-0 flex-col">
        {/* Имя переносится, а не обрезается: «КРМОО "Конноспортивный центр
            Каприоль"» после обрезки неотличимо от любого другого КРМОО. */}
        <span className="line-clamp-2 whitespace-normal max-sm:line-clamp-none max-sm:font-medium">
          {row.name}
        </span>
        {/* Чем возник долг. У Каприоля это два отчёта комиссионера, а не
            отгрузки, и без подстрочника «2 документа на 98 125 ₽» рядом
            с шестнадцатью отгрузками в разборе выглядит ошибкой. */}
        <span className="text-xs text-muted-foreground">{source(row)}</span>
      </span>
    ),
  },
  {
    key: "debt",
    label: "Долг",
    numeric: true,
    strong: true,
    sortKey: "debt",
    changeValue: (row) => row.debt_kopecks,
    render: (row) => formatMoney(row.debt_kopecks),
    explain: (
      <Explain>
        Сумма документов минус оплаченное — то, что ещё не пришло. Переплата
        долгом не считается. <b>Товар, отгруженный по договору комиссии,
        сюда не входит</b>: деньги по нему приходят отчётом комиссионера,
        и сам отчёт в долге уже есть — иначе один и тот же товар был бы
        посчитан дважды.
      </Explain>
    ),
  },
  {
    key: "share",
    label: "Доля",
    numeric: true,
    hideOn: ["narrow"],
    changeValue: (row) => row.debt_share,
    render: (row) => formatShare(row.debt_share),
    explain: (
      <Explain>
        Какую часть <b>всей дебиторки</b> занимает этот контрагент. Поиск
        в знаменатель не входит: набрав «пмт», человек сужает список строк,
        а не то, сколько нам должны. Расчёты через площадку в знаменатель
        не входят тоже — они в отдельном блоке под таблицей.
      </Explain>
    ),
  },
  {
    key: "documents",
    label: "Документов",
    numeric: true,
    sortKey: "documents",
    hideOn: ["narrow", "phone"],
    changeValue: (row) => row.documents_count,
    render: (row) => row.documents_count,
  },
  {
    key: "overdue",
    label: "Просрочено",
    numeric: true,
    // На телефоне карточка оставляет то, ради чего экран открывают: долг,
    // долю и возраст. Просрочка встанет рядом, когда перестанет быть
    // прочерком у всех.
    hideOn: ["phone"],
    changeValue: (row) => overdueOf(row).debt_kopecks,
    render: (row) => {
      const overdue = overdueOf(row)
      if (overdue.count === 0) {
        // Прочерк, а не ноль: ноль означал бы «срок соблюдён», а сегодня
        // срока не существует вовсе.
        return <span className="text-muted-foreground">—</span>
      }
      return (
        <span className="flex flex-col items-end">
          <span className="font-medium text-destructive">
            {formatMoney(overdue.debt_kopecks)}
          </span>
          <span className="text-xs text-muted-foreground">
            {withPlural(overdue.count, "документ", "документа", "документов")}
          </span>
        </span>
      )
    },
    explain: (
      <Explain>
        Долг, у которого <b>вышел срок оплаты</b> — дата документа плюс дни
        отсрочки. Это не то же, что возраст: возраст есть всегда, а просрочка
        только там, где договорённость записана в учёте. Прочерк означает
        «срок посчитать не из чего», а не «всё в порядке»: отсрочка
        не заполнена ни у одного контрагента.
      </Explain>
    ),
  },
  {
    key: "oldest",
    // Коротко в шапке, полностью в карточке телефона. На 900 точках
    // «СТАРЕЙШИЙ ДОЛГ» рядом с «ПРОСРОЧЕНО» выталкивал колонку за край:
    // шесть колонок и боковое меню в 900 точек не помещаются.
    label: "Старейший",
    cardLabel: "Старейший долг",
    numeric: true,
    sortKey: "oldest",
    changeValue: (row) => row.oldest_age_days,
    render: (row) => withPlural(row.oldest_age_days, "день", "дня", "дней"),
    explain: (
      <Explain>
        Сколько дней висит самый старый неоплаченный документ. <b>Не
        просрочка</b>: срок оплаты считается из отсрочки, а она не задана
        ни у одного контрагента — значит сказать «просрочено» не о чем.
        Возраст же есть всегда, и он отделяет вчерашнюю отгрузку от той,
        что ждёт с апреля. Не медиана: платить заставляет самый застарелый
        долг, а не типичный.
      </Explain>
    ),
  },
]

/** Просроченная часть долга строки. Считается из групп, пришедших с ней. */
function overdueOf(row: DeadlineRow): { count: number; debt_kopecks: number } {
  const group = row.groups.find((entry) => entry.key === "overdue")
  return group ?? { count: 0, debt_kopecks: 0 }
}

/**
 * Чем возник долг: отгрузками или отчётами комиссионера.
 *
 * Собирается из `kinds`, а не из числа документов: у Каприоля два документа,
 * и оба — отчёты, а отгрузок по комиссии у него шестнадцать. Не назови мы
 * вид, строка и разбор выглядели бы про разное.
 */
function source(row: DeadlineRow): string {
  const parts: string[] = []
  const demands = row.kinds.demand ?? 0
  const reports = row.kinds.commission_report ?? 0

  if (demands > 0) {
    parts.push(withPlural(demands, "отгрузка", "отгрузки", "отгрузок"))
  }
  if (reports > 0) {
    parts.push(
      withPlural(reports, "отчёт комиссионера", "отчёта комиссионера", "отчётов комиссионера")
    )
  }
  if (row.channels.length > 0) {
    parts.push(row.channels.join(", "))
  }
  return parts.join(" · ")
}

/**
 * По чему эта таблица умеет сортировать — выводится из самих колонок.
 *
 * Второй список неизбежно разъехался бы с первым: колонку добавляют,
 * а перечень ключей забывают — и ссылка с новым порядком приходит
 * к экрану ошибки вместо таблицы.
 */
export const SORT_KEYS: readonly string[] = COLUMNS.flatMap((column) =>
  column.sortKey ? [column.sortKey] : []
)

/**
 * Итог по всей выборке, а не по видимой странице.
 *
 * Живёт рядом с колонками, а не на странице: подвал задаётся **их ключами**,
 * и опечатка в ключе даёт пустую ячейку молча.
 *
 * Возраст в итоге — «до 93 дней», а не сумма и не среднее: складывать
 * возрасты бессмысленно, а среднее по двум контрагентам ничего не решает.
 * Решает самый старый.
 */
export function totalsFor(totals: Deadlines["totals"]): Totals {
  return {
    label: `Итого · ${withPlural(totals.counterparties_count, "контрагент", "контрагента", "контрагентов")}`,
    values: {
      debt: formatMoney(totals.debt_kopecks),
      share: formatShare(totals.debt_share),
      documents: totals.documents_count,
      // Итог просрочки живёт в сводке под таблицей, а не здесь: он про всю
      // дебиторку, а подвал — про показанные строки. Свести их в одну ячейку
      // значило бы сложить два множества.
      overdue: <span className="text-muted-foreground">—</span>,
      oldest:
        totals.oldest_age_days === null ? (
          <span className="text-muted-foreground">—</span>
        ) : (
          `до ${withPlural(totals.oldest_age_days, "дня", "дней", "дней")}`
        ),
    },
  }
}
