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
  Regex,
  LayoutDashboard,
  type LucideIcon,
  Scale,
  Tags,
  Users,
  AtSign,
  FileUp,
  Mail,
  Settings2,
  ShieldCheck,
  Store,
  Truck,
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
import type { MeOut } from "@/lib/api/generated/types.gen";
import { type AccessKey, can } from "@/lib/access";
import { BrandMark, useBranding } from "@/lib/branding";
import { ROLE_LABELS } from "@/lib/roles";

// Staff items follow the Page access matrix (`page`); `customer` items show to customers.
type NavItem = {
  title: string;
  href: string;
  icon: LucideIcon;
  page?: AccessKey;
  customer?: boolean;
  soon?: boolean;
};

const NAV: { label: string; items: NavItem[] }[] = [
  {
    label: "Overview",
    items: [
      {
        title: "Dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
        page: "dashboard",
        customer: true,
      },
    ],
  },
  {
    label: "Complaints",
    items: [
      { title: "Submit a complaint", href: "/complaints/new", icon: FilePlus2, customer: true },
      { title: "My complaints", href: "/complaints", icon: ClipboardList, customer: true },
      { title: "Complaint queue", href: "/complaints", icon: Inbox, page: "complaints" },
      { title: "Enquiries", href: "/enquiries", icon: Mail, page: "enquiries" },
      { title: "Mailbox", href: "/mailbox", icon: AtSign, page: "mailbox" },
      { title: "Orders", href: "/fulfilment", icon: Truck, page: "orders" },
      { title: "Import complaints", href: "/imports", icon: FileUp, page: "imports" },
      { title: "Manual review", href: "/review", icon: Scale, page: "review" },
      { title: "Analytics", href: "/analytics", icon: BarChart3, page: "analytics" },
      { title: "Reports", href: "/reports", icon: FileBarChart, page: "reports" },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { title: "Knowledge base", href: "/knowledge-base", icon: BookOpen, page: "knowledge_base" },
    ],
  },
  {
    label: "Administration",
    items: [
      { title: "Taxonomy & SLAs", href: "/settings/taxonomy", icon: Tags, page: "taxonomy" },
      { title: "Rule matrix", href: "/settings/rules", icon: ListChecks, page: "rules" },
      { title: "Products", href: "/settings/products", icon: Package, page: "products" },
      { title: "Users & roles", href: "/settings/users", icon: Users, page: "users" },
      { title: "Page access", href: "/settings/access", icon: ShieldCheck, page: "access" },
      { title: "Settings", href: "/settings/general", icon: Settings2, page: "settings" },
      { title: "Patterns", href: "/settings/patterns", icon: Regex, page: "settings" },
    ],
  },
];

function visible(item: NavItem, user: MeOut): boolean {
  if (user.role === "customer") return Boolean(item.customer);
  return item.page !== undefined && can(user, item.page);
}

function isActive(pathname: string, href: string) {
  if (href === "/complaints") return pathname === href || /^\/complaints\/CMP-/i.test(pathname);
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppSidebar({ user }: { user: MeOut }) {
  const pathname = usePathname();
  const consoleName = useBranding().data?.console_name ?? "SupportNova";
  const groups = NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => visible(item, user)),
  })).filter((group) => group.items.length > 0);

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <Link href="/dashboard" className="flex items-center gap-2 px-2 py-1.5">
          <BrandMark target="console" className="size-7 rounded-md" />
          <span className="font-semibold group-data-[collapsible=icon]:hidden">{consoleName}</span>
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
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="Back to shop">
              <Link href="/">
                <Store />
                <span>Back to shop</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <div className="px-2 pb-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
          Signed in as <span className="font-medium text-foreground">{ROLE_LABELS[user.role]}</span>
          {user.department ? ` · ${user.department.name}` : null}
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
