import type {
  ShipmentProductRow,
  ShipmentProductsQuery,
} from "@/sections/shipments-products/api"
import { RowDetail } from "@/sections/shipments-products/ui/row-detail"
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
  return (
    <Drawer open={row !== null} onOpenChange={(open: boolean) => !open && onClose()}>
      <DrawerContent>
        {row ? (
          <>
            <DrawerHeader>
              <DrawerTitle className="text-left">{row.name}</DrawerTitle>
              <DrawerDescription className="text-left font-mono text-xs">
                {[row.code, row.article].filter(Boolean).join(" · ")}
              </DrawerDescription>
            </DrawerHeader>
            <div className="overflow-y-auto pb-4">
              <RowDetail row={row} query={query} repeatRowNumbers />
            </div>
          </>
        ) : null}
      </DrawerContent>
    </Drawer>
  )
}
