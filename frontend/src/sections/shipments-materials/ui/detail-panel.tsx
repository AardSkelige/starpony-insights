import type {
  ShipmentMaterialRow,
  ShipmentMaterialsQuery,
} from "@/sections/shipments-materials/api"
import { RowDetail } from "@/sections/shipments-materials/ui/row-detail"
import { DetailDrawer } from "@/shared/components/detail-drawer"
import { useScreen } from "@/shared/hooks/use-screen"

/**
 * Разбор материала для узкого экрана и телефона.
 *
 * Панель выезжает поверх списка, поэтому числа самой строки в ней
 * повторяются: строка закрыта затемнением, свериться с ней нельзя.
 */
export function DetailPanel({
  row,
  query,
  onClose,
}: {
  row: ShipmentMaterialRow | null
  query: Omit<ShipmentMaterialsQuery, "page">
  onClose: () => void
}) {
  const screen = useScreen()

  return (
    <DetailDrawer
      open={row !== null}
      title={row?.name ?? ""}
      subtitle={
        row ? [row.code, row.article, row.uom].filter(Boolean).join(" · ") : undefined
      }
      onClose={onClose}
    >
      {row ? (
        <RowDetail
          row={row}
          query={query}
          repeatRowNumbers
          tabbed={screen === "phone"}
        />
      ) : null}
    </DetailDrawer>
  )
}
