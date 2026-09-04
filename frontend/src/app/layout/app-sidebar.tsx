import { NavLink, useLocation, useNavigate } from "react-router"
import { ChevronsUpDown, LogOut, Settings } from "lucide-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { splitNavigation } from "@/app/layout/nav-groups"
import { FALLBACK_ICON, NAV_ICONS } from "@/app/layout/nav-icons"
import { SidebarResizer } from "@/app/layout/sidebar-controls"
import type { Page, Profile } from "@/shared/api/client"
import { Logo } from "@/shared/components/logo"
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
  useSidebar,
} from "@/shared/ui/sidebar"

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).slice(0, 2)
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("") || "?"
}

function PageLink({ page }: { page: Page }) {
  const Icon = NAV_ICONS[page.key] ?? FALLBACK_ICON
  const { pathname } = useLocation()
  const { isMobile, setOpenMobile } = useSidebar()

  // `NavLink` сам по себе пункт не подсветит: `SidebarMenuButton` красит
  // по своему пропу `isActive`, а не по `aria-current`, который ставит ссылка.
  // Вложенные пути тоже считаются активными — «/shipments/products/42»
  // остаётся тем же разделом меню.
  const active =
    page.route === "/"
      ? pathname === "/"
      : pathname === page.route || pathname.startsWith(`${page.route}/`)

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        isActive={active}
        tooltip={{ children: page.label, sideOffset: 10 }}
        render={
          <NavLink
            to={page.route}
            end={page.route === "/"}
            // На телефоне плавный переход между экранами выключен намеренно.
            // Меню закрывается в тот же кадр, и две анимации — уезжающая
            // панель и снимок перехода — спорят: панель успевает дёрнуться
            // и пропасть. Самого перехода всё равно не видно: его закрывает
            // меню, которое в этот момент ещё на экране.
            viewTransition={!isMobile}
            // Оставить меню открытым над только что выбранным разделом —
            // значит закрыть собой то, ради чего по пункту и нажали.
            onClick={() => isMobile && setOpenMobile(false)}
          >
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
                  <div className="flex aspect-square size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                    <Logo className="size-7" />
                  </div>
                  <div className="grid flex-1 text-left leading-tight">
                    <span className="truncate font-semibold">StarPony</span>
                    <span className="truncate text-xs text-muted-foreground">
                      Insights
                    </span>
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
                      <span className="truncate font-medium">
                        {profile.full_name}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {/* Должность, а не права. Собирает её сервер
                            (`User.sidebar_title`): «Полный доступ» остаётся
                            запасным вариантом, пока должность не заполнена,
                            и решать это в двух местах нельзя. */}
                        {profile.title}
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
                  {/* Админка — только суперпользователю, и только здесь:
                      пунктом меню она стояла бы наравне с разделами, хотя
                      это не раздел, а служебный вход. Django пускает внутрь
                      сам, по `is_staff`, — наша проверка лишь прячет ссылку
                      у тех, кому она всё равно ответит формой входа.

                      Обычная ссылка, а не `Link`: админка живёт вне
                      React-приложения, и роутер по ней перейти не может. */}
                  {profile.is_superuser ? (
                    <DropdownMenuItem
                      render={
                        <a href="/admin/" target="_blank" rel="noreferrer">
                          <Settings />
                          Админка
                        </a>
                      }
                    />
                  ) : null}
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
