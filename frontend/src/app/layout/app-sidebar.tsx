import { NavLink, useNavigate } from "react-router"
import { ChevronsUpDown, LogOut } from "lucide-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { splitNavigation } from "@/app/layout/nav-groups"
import { FALLBACK_ICON, NAV_ICONS } from "@/app/layout/nav-icons"
import { SidebarResizer } from "@/app/layout/sidebar-controls"
import type { Page, Profile } from "@/shared/api/client"
import { signOut } from "@/shared/auth/session"
import { Avatar, AvatarFallback } from "@/shared/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/shared/ui/sidebar"

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).slice(0, 2)
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("") || "?"
}

function PageLink({ page }: { page: Page }) {
  const Icon = NAV_ICONS[page.key] ?? FALLBACK_ICON
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        tooltip={{ children: page.label, sideOffset: 10 }}
        render={
          <NavLink to={page.route} end={page.route === "/"} viewTransition>
            {/* Развёрнутый сайдбар текстовый — читается как оглавление,
                а не как панель инструментов. Иконка нужна
                только в свёрнутом рельсе, где показывать больше нечего. */}
            <Icon className="hidden group-data-[collapsible=icon]:block" />
            <span>{page.label}</span>
          </NavLink>
        }
      />
    </SidebarMenuItem>
  )
}

export function AppSidebar({
  profile,
  onResize,
  onCommitWidth,
  onResetWidth,
}: {
  profile: Profile
  onResize: (width: number) => void
  onCommitWidth: (width: number) => void
  onResetWidth: () => void
}) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const logout = useMutation({
    mutationFn: signOut,
    onSettled: () => {
      // Уводим со страницы сами, а не ждём, пока защита маршрута заметит
      // пропавшую сессию: наблюдатели запроса могут отдать старые данные,
      // и человек остаётся в приложении, из которого уже вышел.
      queryClient.clear()
      navigate("/login", { replace: true, viewTransition: true })
    },
  })

  const { top, groups } = splitNavigation(profile.pages)

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            {/* Без подсказки: логотип и так очевиден, а в свёрнутом виде
                плашка перекрывала бы хлебные крошки рядом. */}
            <SidebarMenuButton
              size="lg"
              render={
                <NavLink to="/" end viewTransition>
                  <div className="flex aspect-square size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-xs font-semibold text-primary-foreground">
                    SP
                  </div>
                  <div className="grid flex-1 text-left leading-tight">
                    <span className="truncate font-semibold">StarPony</span>
                    <span className="truncate text-xs text-muted-foreground">Insights</span>
                  </div>
                </NavLink>
              }
            />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {top.length > 0 ? (
          <SidebarGroup className="group-data-[collapsible=icon]:px-2 group-data-[collapsible=icon]:py-0">
            <SidebarGroupContent>
              <SidebarMenu>
                {top.map((page) => (
                  <PageLink key={page.key} page={page} />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ) : null}

        {groups.map((group) => (
          <SidebarGroup
            key={group.label}
            className="pl-4.5 group-data-[collapsible=icon]:px-2 group-data-[collapsible=icon]:py-0"
          >
            {/* pointer-events-none в рельсе: свёрнутый заголовок компонент прячет
                прозрачностью и сдвигает на -32px вверх, но из потока не убирает —
                невидимый, он ложится поверх кнопок соседней группы и съедает
                наведение. Отсюда «иконки не реагируют, кроме последней». */}
            <SidebarGroupLabel className="-ml-2.5 group-data-[collapsible=icon]:pointer-events-none">
              {group.label}
            </SidebarGroupLabel>
            {/* Группа отчёркнута рельсой слева: пункты читаются как список
                под заголовком, а не как ровная лента без деления.
                Отступ задан родителю: у содержимого ширина во всю группу,
                и собственный отступ вытолкнул бы подсветку за правый край. */}
            <SidebarGroupContent className="border-l pl-1.5 group-data-[collapsible=icon]:border-l-0 group-data-[collapsible=icon]:pl-0">
              <SidebarMenu>
                {group.pages.map((page) => (
                  <PageLink key={page.key} page={page} />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <SidebarMenuButton size="lg">
                    {/* after:rounded-lg — обводку компонент рисует псевдоэлементом, и она
                        остаётся круглой, даже когда сам блок скруглён по-другому. */}
                    <Avatar className="size-8 rounded-lg after:rounded-lg">
                      <AvatarFallback className="rounded-lg bg-secondary text-xs text-secondary-foreground">
                        {initials(profile.full_name)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="grid flex-1 text-left leading-tight">
                      <span className="truncate font-medium">{profile.full_name}</span>
                      <span className="truncate text-xs text-muted-foreground">
                        {profile.is_superuser ? "Полный доступ" : "Сотрудник"}
                      </span>
                    </div>
                    <ChevronsUpDown className="ml-auto" />
                  </SidebarMenuButton>
                }
              />
              {/* Ширина по кнопке: меню уже кнопки выглядит обрезанным,
                  шире — вылезает за край сайдбара. */}
              <DropdownMenuContent
                align="end"
                side="top"
                sideOffset={4}
                className="w-(--anchor-width) min-w-56"
              >
                <DropdownMenuGroup>
                  <DropdownMenuItem
                    disabled={logout.isPending}
                    onClick={() => logout.mutate()}
                  >
                    <LogOut />
                    Выйти
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarResizer
        onResize={onResize}
        onCommit={onCommitWidth}
        onReset={onResetWidth}
      />
    </Sidebar>
  )
}
