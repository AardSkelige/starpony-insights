import type {
  ShipmentProductRow,
  ShipmentProductsQuery,
} from "@/sections/shipments-products/api"
import { RowDetail } from "@/sections/shipments-products/ui/row-detail"
import { useScreen } from "@/shared/hooks/use-screen"
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/shared/ui/drawer"

/**
 * Детали строки для узкого экрана и телефона.
 *
 * Панель выезжает поверх списка, поэтому числа самой строки в ней
 * повторяются: строка закрыта затемнением, свериться с ней нельзя.
 * На широком экране те же детали раскрываются прямо в строке — и там
 * повтор не нужен.
 */
export function DetailPanel({
  row,
  query,
  onClose,
}: {
  row: ShipmentProductRow | null
  query: Omit<ShipmentProductsQuery, "page">
  onClose: () => void
}) {
  const screen = useScreen()

  return (
    // `showSwipeHandle` — полоска сверху, за которую панель тянут вниз.
    // Без неё непонятно, что панель вообще двигается пальцем.
    <Drawer
      open={row !== null}
      onOpenChange={(open: boolean) => !open && onClose()}
      showSwipeHandle
    >
      <DrawerContent>
        {row ? (
          <>
            <DrawerHeader>
              <DrawerTitle className="text-left">{row.name}</DrawerTitle>
              <DrawerDescription className="text-left font-mono text-xs">
                {[row.code, row.article].filter(Boolean).join(" · ")}
              </DrawerDescription>
            </DrawerHeader>
            <div className="overflow-y-auto px-4 pb-6">
              <RowDetail
                row={row}
                query={query}
                repeatRowNumbers
                tabbed={screen === "phone"}
              />
            </div>
          </>
        ) : null}
      </DrawerContent>
    </Drawer>
  )
}
