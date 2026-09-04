import * as React from "react"

import { DetailDrawer } from "@/shared/components/detail-drawer"
import { useScreen } from "@/shared/hooks/use-screen"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/shared/ui/sheet"

/**
 * Панель со списком: сбоку на большом экране, снизу на телефоне.
 *
 * **Форма зависит от ширины, и это правило `DESIGN.md` §6, а не вкус.**
 * Панель снизу занимает всю ширину монитора ради колонки в четыреста точек —
 * список из двух колонок растягивается на два метра пустоты, а страница
 * под ним скрывается целиком. Сбоку она встаёт рядом с плиткой, из которой
 * открыта, и та остаётся на виду: видно, к какому числу относится список.
 *
 * На телефоне обратное: панель сбоку там — это та же панель во всю ширину,
 * только с рывком вбок, а нижняя закрывается смахиванием.
 *
 * Отдельно от `DetailDrawer`: тот отвечает за разбор строки таблицы,
 * и добавлять ему второй облик значило бы решать здесь за восемь страниц,
 * у которых на широком экране разбор раскрывается прямо в строке.
 */
export function SidePanel({
  open,
  title,
  subtitle,
  onClose,
  children,
}: {
  open: boolean
  title: string
  subtitle: string
  onClose: () => void
  children: React.ReactNode
}) {
  const screen = useScreen()

  if (screen === "phone") {
    return (
      <DetailDrawer open={open} title={title} onClose={onClose}>
        <p className="pb-2 text-xs text-muted-foreground">{subtitle}</p>
        {children}
      </DetailDrawer>
    )
  }

  return (
    <Sheet open={open} onOpenChange={(next: boolean) => !next && onClose()}>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>{subtitle}</SheetDescription>
        </SheetHeader>
        {/* Прокручивается только содержимое: иначе панель меняет высоту
            под каждый список и дёргается при открытии. */}
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6">{children}</div>
      </SheetContent>
    </Sheet>
  )
}
