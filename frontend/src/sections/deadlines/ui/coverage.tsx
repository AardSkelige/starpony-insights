import type { Deadlines } from "@/sections/deadlines/api"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { Explain } from "@/shared/components/explain"
import { formatMoney } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

type Coverage = Deadlines["coverage"]

/**
 * Вся картина расчётов — тремя суммами в сворачиваемом блоке под таблицей.
 *
 * **Три числа, а не одно.** Дебиторка, расчёты через площадку и товар
 * на реализации приходят из одного места учёта — «отгружено и не оплачено», —
 * и складываются в число, которое выглядит правдой: 890 209,57 ₽ «долга»,
 * из которых нам должны 176 360,15 ₽. Блок существует ради того, чтобы
 * этот вопрос не задавали вслух каждый раз.
 *
 * Под таблицей и свёрнут — как на четырёх соседних страницах: раздел обязан
 * открываться одинаково везде.
 */
export function Coverage({ coverage }: { coverage: Coverage }) {
  return (
    <CollapsibleNote title="Вся картина расчётов" headline={headline(coverage)}>
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
        <Stat
          label="Нам должны"
          value={formatMoney(coverage.debt_kopecks)}
          note={`${withPlural(coverage.counterparties_count, "контрагент", "контрагента", "контрагентов")} · ${withPlural(coverage.documents_count, "документ", "документа", "документов")}`}
          explain={
            <Explain>
              Долг покупателей: сумма документов минус оплаченное. Это
              единственная из трёх сумм, по которой <b>звонят</b>, — две
              другие означают «деньги придут сами».
            </Explain>
          }
        />
        <Stat
          label="Ждём выплату площадки"
          value={formatMoney(coverage.marketplace_kopecks)}
          note={`${withPlural(coverage.marketplaces_count, "площадка", "площадки", "площадок")} · ${withPlural(coverage.marketplace_documents_count, "документ", "документа", "документов")}`}
          quiet
          explain={
            <Explain>
              Отгружено площадкам, помеченным в учёте группой{" "}
              <b>«маркетплейсы»</b>. Выплата приходит реестром раз в цикл
              и в МойСклад не заводится, поэтому такая отгрузка остаётся
              неоплаченной навсегда. Долгом это не считается: сверка идёт
              в кабинете площадки.
            </Explain>
          }
        />
        <Stat
          label="Товар на реализации"
          value={formatMoney(coverage.consignment_kopecks)}
          note={`${withPlural(coverage.consignment_count, "отгрузка", "отгрузки", "отгрузок")} · ${withPlural(coverage.consignment_counterparties_count, "комиссионер", "комиссионера", "комиссионеров")}`}
          quiet
          explain={
            <Explain>
              Отгружено по договорам комиссии. У таких отгрузок оплата
              не заполняется никогда: деньги приходят <b>отчётом
              комиссионера</b>, когда товар продадут, — и эти отчёты уже
              посчитаны в долге слева. Считать оба значило бы посчитать
              один и тот же товар дважды. Комиссионеров здесь может быть
              больше, чем строк в таблице: у того, чьи отчёты оплачены,
              долга нет, а товар на реализации лежит.
            </Explain>
          }
        />
      </div>

      {coverage.overdue_kopecks > 0 || coverage.soon_kopecks > 0 ? (
        <p className="mt-3 text-sm">
          <span className="font-medium text-destructive">
            Просрочено {formatMoney(coverage.overdue_kopecks)}
          </span>
          <span className="text-muted-foreground">
            {" "}
            из {formatMoney(coverage.debt_kopecks)} ·{" "}
            {withPlural(coverage.overdue_count, "документ", "документа", "документов")}
          </span>
          {coverage.soon_kopecks > 0 ? (
            <span className="text-muted-foreground">
              . Срок подходит у{" "}
              {withPlural(coverage.soon_count, "документа", "документов", "документов")}{" "}
              на {formatMoney(coverage.soon_kopecks)}
            </span>
          ) : null}
        </p>
      ) : null}

      <p className="mt-3 text-xs text-muted-foreground">{deferralNote(coverage)}</p>
    </CollapsibleNote>
  )
}

/** Главное число — видно и в свёрнутом виде. */
function headline(coverage: Coverage): string {
  const whole =
    coverage.debt_kopecks +
    coverage.marketplace_kopecks +
    coverage.consignment_kopecks

  return `нам должны ${formatMoney(coverage.debt_kopecks)} из ${formatMoney(whole)} отгруженного и не закрытого`
}

/**
 * Почему на странице нет слова «просрочено».
 *
 * Не жалоба на данные, а инструкция: поле в учёте есть, оно просто пустое,
 * и заполнить его может владелец без нашего участия.
 */
function deferralNote(coverage: Coverage): string {
  if (coverage.with_deferral_count === 0) {
    return (
      `Отсрочка не задана ни у одного из ${coverage.counterparties_total} контрагентов, ` +
      "поэтому срок оплаты посчитать не из чего — страница считает возраст долга. " +
      "Заполните «Срок отсрочки (дней)» в карточке контрагента, и появятся группы " +
      "«просрочено», «скоро истекает», «в норме»."
    )
  }
  return (
    `Отсрочка задана у ${coverage.with_deferral_count} из ${coverage.counterparties_total} контрагентов. ` +
    "У остальных срок оплаты посчитать не из чего — там показан возраст долга."
  )
}

function Stat({
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
   * Число приглушено: это не долг, а деньги, которые придут сами.
   * Набери их наравне с дебиторкой — и глаз сложит все три.
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
