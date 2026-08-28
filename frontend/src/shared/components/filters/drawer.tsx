import { SlidersHorizontal } from "lucide-react"

import { Filters, type FilterValue } from "@/shared/components/filters"
import type { SalesChannel } from "@/shared/api/types"
import { DRAWER_HANDLE } from "@/shared/components/drawer-handle"
import { Button } from "@/shared/ui/button"
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/shared/ui/drawer"

/**
 * Фильтры на телефоне: кнопка и выдвижная панель снизу.
 *
 * Ряд из четырёх полей на экране шириной 390 точек занял бы три строки
 * и оттеснил бы таблицу вниз, ради которой страницу и открывают.
 */
export function FiltersDrawer({
  value,
  onChange,
  onReset,
  channels,
  searchPlaceholder,
  searchLabel,
  activeCount,
}: {
  value: FilterValue
  onChange: (patch: Partial<FilterValue>) => void
  onReset: () => void
  channels: SalesChannel[]
  searchPlaceholder: string
  searchLabel: string
  activeCount: number
}) {
  return (
    <Drawer>
      <DrawerTrigger
        render={
          <Button variant="outline" className="h-10 w-full sm:hidden">
            <SlidersHorizontal data-icon="inline-start" />
            Фильтры
            {activeCount > 0 ? ` · ${activeCount}` : ""}
          </Button>
        }
      />
      <DrawerContent className={DRAWER_HANDLE}>
        <DrawerHeader>
          <DrawerTitle className="text-left">Фильтры</DrawerTitle>
        </DrawerHeader>
        <div className="flex flex-col gap-3 px-4 pb-6">
          <Filters
            value={value}
            onChange={onChange}
            onReset={onReset}
            channels={channels}
            searchPlaceholder={searchPlaceholder}
            searchLabel={searchLabel}
            stacked
          />
        </div>
      </DrawerContent>
    </Drawer>
  )
}
