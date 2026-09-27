"use client";

import {
  BarChart3,
  BookOpen,
  ClipboardList,
  FileBarChart,
  FilePlus2,
  Inbox,
  ListChecks,
  Package,
  LayoutDashboard,
  type LucideIcon,
  Scale,
  Tags,
  Users,
  AtSign,
  FileUp,
  Mail,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import type { Role, UserOut } from "@/lib/api/generated/types.gen";
import { ROLE_LABELS } from "@/lib/roles";

type NavItem = { title: string; href: string; icon: LucideIcon; roles: Role[]; soon?: boolean };

const ALL: Role[] = ["customer", "agent", "reviewer", "manager", "admin"];
const STAFF: Role[] = ["agent", "reviewer", "manager", "admin"];

const NAV: { label: string; items: NavItem[] }[] = [
  {
    label: "Overview",
    items: [{ title: "Dashboard", href: "/dashboard", icon: LayoutDashboard, roles: ALL }],
  },
  {
    label: "Complaints",
    items: [
      {
        title: "Submit a complaint",
        href: "/complaints/new",
        icon: FilePlus2,
        roles: ["customer"],
      },
      {
        title: "My complaints",
        href: "/complaints",
        icon: ClipboardList,
        roles: ["customer"],
      },
      { title: "Complaint queue", href: "/complaints", icon: Inbox, roles: STAFF },
      { title: "Enquiries", href: "/enquiries", icon: Mail, roles: STAFF },
      { title: "Mailbox", href: "/mailbox", icon: AtSign, roles: STAFF },
      {
        title: "Import complaints",
        href: "/imports",
        icon: FileUp,
        roles: ["manager", "admin"],
      },
      {
        title: "Manual review",
        href: "/review",
        icon: Scale,
        roles: ["reviewer", "manager", "admin"],
      },
      {
        title: "Analytics",
        href: "/analytics",
        icon: BarChart3,
        roles: ["reviewer", "manager", "admin"],
      },
      {
        title: "Reports",
        href: "/reports",
        icon: FileBarChart,
        roles: ["reviewer", "manager", "admin"],
      },
    ],
  },
  {
    label: "Knowledge",
    items: [{ title: "Knowledge base", href: "/knowledge-base", icon: BookOpen, roles: STAFF }],
  },
  {
    label: "Administration",
    items: [
      { title: "Taxonomy & SLAs", href: "/settings/taxonomy", icon: Tags, roles: STAFF },
      { title: "Rule matrix", href: "/settings/rules", icon: ListChecks, roles: STAFF },
      { title: "Products", href: "/settings/products", icon: Package, roles: ["admin"] },
      { title: "Users & roles", href: "/settings/users", icon: Users, roles: ["manager", "admin"] },
    ],
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/complaints") return pathname === href || /^\/complaints\/CMP-/i.test(pathname);
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppSidebar({ user }: { user: UserOut }) {
  const pathname = usePathname();
  const groups = NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => item.roles.includes(user.role)),
  })).filter((group) => group.items.length > 0);

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <Link href="/dashboard" className="flex items-center gap-2 px-2 py-1.5">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
            SN
          </span>
          <span className="font-semibold group-data-[collapsible=icon]:hidden">SupportNova</span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        {groups.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  {item.soon ? (
                    <SidebarMenuButton disabled tooltip={`${item.title} (coming soon)`}>
                      <item.icon />
                      <span>{item.title}</span>
                      <Badge variant="outline" className="ml-auto text-[10px]">
                        Soon
                      </Badge>
                    </SidebarMenuButton>
                  ) : (
                    <SidebarMenuButton
                      asChild
                      isActive={isActive(pathname, item.href)}
                      tooltip={item.title}
                    >
                      <Link href={item.href}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  )}
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <div className="px-2 pb-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
          Signed in as <span className="font-medium text-foreground">{ROLE_LABELS[user.role]}</span>
          {user.department ? ` · ${user.department.name}` : null}
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
