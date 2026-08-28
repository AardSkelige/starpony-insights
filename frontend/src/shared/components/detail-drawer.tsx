import {
  DRAWER_HANDLE,
  DRAWER_PHONE_HEIGHT,
} from "@/shared/components/drawer-handle"
import { cn } from "@/shared/lib/utils"
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/shared/ui/drawer"

/**
 * Панель разбора строки для узкого экрана и телефона.
 *
 * Что внутри — дело раздела, а как панель устроена — общее: полоска для
 * сворачивания, фиксированная высота на телефоне и прокрутка только
 * содержимого. Последнее важно: без него панель меняет высоту при каждой
 * подгрузке и дёргается на глазах.
 */
export function DetailDrawer({
  open,
  title,
  subtitle,
  onClose,
  children,
}: {
  open: boolean
  title: string
  subtitle?: string
  onClose: () => void
  children: React.ReactNode
}) {
  return (
    <Drawer open={open} onOpenChange={(next: boolean) => !next && onClose()}>
      <DrawerContent className={cn(DRAWER_HANDLE, DRAWER_PHONE_HEIGHT)}>
        <DrawerHeader>
          <DrawerTitle className="text-left">{title}</DrawerTitle>
          {subtitle ? (
            <DrawerDescription className="text-left font-mono text-xs">
              {subtitle}
            </DrawerDescription>
          ) : null}
        </DrawerHeader>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6">{children}</div>
      </DrawerContent>
    </Drawer>
  )
}
