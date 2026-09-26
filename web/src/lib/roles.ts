import type { Role } from "@/lib/api/generated/types.gen";

export const ROLE_LABELS: Record<Role, string> = {
  customer: "Customer",
  agent: "Support Agent",
  reviewer: "Reviewer",
  manager: "Support Manager",
  admin: "Administrator",
};

export const STAFF_ROLES: Role[] = ["agent", "reviewer", "manager", "admin"];

export const isStaff = (role: Role) => STAFF_ROLES.includes(role);
