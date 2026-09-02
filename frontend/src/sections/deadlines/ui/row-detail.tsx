import { useDeadlineDetail, type DeadlineRow } from "@/sections/deadlines/api"
import { Documents } from "@/sections/deadlines/ui/documents"
import { Consignment } from "@/sections/deadlines/ui/consignment"
import { FailedPanel } from "@/shared/components/detail/failed-panel"

/**
 * Разбор строки: из чего сложился долг контрагента.
 *
 * Два блока, и второй появляется редко. Первый — сами документы с возрастом
 * и сроком оплаты; второй — товар по договорам комиссии, который долгом
 * не считается и потому объясняет, почему долг такой маленький: у Каприоля
 * 98 125 ₽ при 452 696 ₽ отгруженного.
 *
 * В одну колонку, а не в две: документы — это список, и вторая колонка
 * рядом с ним либо пустует, либо ужимает его вдвое.
 */
export function RowDetail({
  row,
  inDrawer = false,
}: {
  row: DeadlineRow
  /** В выдвижной панели строка закрыта затемнением — её числа надо повторить. */
  inDrawer?: boolean
}) {
  const detail = useDeadlineDetail(row.agent_id)

  // Одно сообщение на всю панель: два одинаковых «Не удалось» с двумя
  // кнопками повторяют один и тот же запрос.
  if (detail.isError) {
    return <FailedPanel onRetry={() => detail.refetch()} />
  }

  return (
    <div className={inDrawer ? "flex flex-col gap-4" : "flex flex-col gap-4 p-4"}>
      <Documents detail={detail} row={row} repeatRowNumbers={inDrawer} />
      <Consignment detail={detail} />
    </div>
  )
}
