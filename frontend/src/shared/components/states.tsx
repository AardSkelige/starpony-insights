import { CloudOff, PackageOpen } from "lucide-react"

import { Button } from "@/shared/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/shared/ui/empty"

/**
 * Данных нет — и это нормально.
 *
 * Подсказка обязательна: пустой экран без объяснения читается как поломка,
 * и человек идёт спрашивать, вместо того чтобы поменять период.
 */
export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string
  hint: string
  action?: React.ReactNode
}) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <PackageOpen />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{hint}</EmptyDescription>
      </EmptyHeader>
      {action ? <EmptyContent>{action}</EmptyContent> : null}
    </Empty>
  )
}

/**
 * Загрузка не удалась.
 *
 * Кнопка повтора обязательна: тупик без выхода вынуждает перезагружать
 * страницу целиком и терять выбранные фильтры.
 */
export function ErrorState({
  onRetry,
  retrying = false,
}: {
  onRetry: () => void
  retrying?: boolean
}) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <CloudOff />
        </EmptyMedia>
        <EmptyTitle>Не удалось загрузить данные</EmptyTitle>
        <EmptyDescription>
          Сессия при этом цела — входить заново не нужно.
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button variant="outline" onClick={onRetry} disabled={retrying}>
          {retrying ? "Пробуем…" : "Попробовать снова"}
        </Button>
      </EmptyContent>
    </Empty>
  )
}
