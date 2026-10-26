"""Page access gate: the default matrix gives exactly today's access, and the matrix is enforced."""

from collections.abc import Callable

import httpx
import pytest

from database.models import Role

pytestmark = pytest.mark.db

ALL = {"agent", "reviewer", "manager", "admin"}
INSIGHT = {"reviewer", "manager", "admin"}
MGR = {"manager", "admin"}
ADMIN = {"admin"}
ID = "00000000-0000-0000-0000-000000000001"
C = "/complaints/CMP-999999"
V = f"/document-versions/{ID}"
P = "/admin/products/VH-NONE"

# Today's access, recorded literally (not derived from the new code): (method, path, roles).
ROUTES: list[tuple[str, str, set[str]]] = [
    ("GET", "/dashboard/agent", ALL),
    ("GET", f"{C}/analysis", ALL),
    ("POST", f"{C}/analyze", ALL),
    ("GET", f"{C}/validation", ALL),
    ("POST", f"{C}/validate", ALL),
    ("GET", f"{C}/decisions", ALL),
    ("PATCH", f"{C}/status", ALL),
    ("GET", f"{C}/chat", ALL),
    ("GET", "/review-queue", INSIGHT),
    ("POST", f"{C}/review", INSIGHT),
    ("GET", "/enquiries", ALL),
    ("PATCH", "/enquiries/ENQ-999999", ALL),
    ("POST", "/enquiries/ENQ-999999/convert", ALL),
    ("GET", "/mailbox", ALL),
    ("GET", "/mailbox/inbound", ALL),
    ("GET", "/mailbox/outbound", ALL),
    ("POST", "/mailbox/process", ALL),
    ("GET", "/admin/orders", ALL),
    ("GET", "/admin/orders/ORD-999999", ALL),
    ("POST", "/admin/orders/ORD-999999/actions", ALL),
    ("GET", "/imports", MGR),
    ("GET", f"/imports/{ID}", MGR),
    ("GET", f"/imports/{ID}/result.csv", MGR),
    ("GET", "/imports/template.csv", MGR),
    ("GET", "/imports/template.xlsx", MGR),
    ("POST", "/imports/preview", MGR),
    ("POST", f"/imports/{ID}/run", MGR),
    ("GET", "/analytics", INSIGHT),
    ("GET", "/dashboard/admin", INSIGHT),
    ("GET", "/reports", INSIGHT),
    ("GET", "/reports/x", INSIGHT),
    ("GET", "/reports/x/export", INSIGHT),
    ("GET", "/documents", ALL),
    ("GET", "/documents/types", ALL),
    ("GET", f"/documents/{ID}", ALL),
    ("GET", f"{V}/file", ALL),
    ("GET", f"{V}/chunks", ALL),
    ("GET", "/knowledge-base/search?q=late", ALL),
    ("POST", "/documents/upload", ADMIN),
    ("POST", f"{V}/activate", ADMIN),
    ("POST", f"{V}/retire", ADMIN),
    ("POST", f"{V}/reprocess", ADMIN),
    ("GET", "/taxonomy/sla-policies", ALL),
    ("POST", "/taxonomy/departments", ADMIN),
    ("PATCH", f"/taxonomy/departments/{ID}", ADMIN),
    ("POST", "/taxonomy/categories", ADMIN),
    ("PATCH", f"/taxonomy/categories/{ID}", ADMIN),
    ("POST", f"/taxonomy/categories/{ID}/subcategories", ADMIN),
    ("PATCH", f"/taxonomy/sla-policies/{ID}", ADMIN),
    ("GET", "/rules", ALL),
    ("GET", "/rules/facts", ALL),
    ("GET", "/rules/export.csv", ALL),
    ("POST", "/rules", ADMIN),
    ("PUT", "/rules/DEL-001", ADMIN),
    ("GET", "/admin/products", ADMIN),
    ("POST", "/admin/products", ADMIN),
    ("PATCH", P, ADMIN),
    ("POST", f"{P}/images", ADMIN),
    ("PUT", f"{P}/images/order", ADMIN),
    ("DELETE", f"{P}/images/{ID}", ADMIN),
    ("GET", "/users", MGR),
    ("PATCH", f"/users/{ID}", ADMIN),
    ("GET", "/settings", ADMIN),
    ("PUT", "/settings", ADMIN),
    ("GET", "/taxonomy/departments", ALL | {"customer"}),
    ("GET", "/taxonomy/categories", ALL | {"customer"}),
    ("GET", "/taxonomy/vocabulary", ALL),
]


async def call(client: httpx.AsyncClient, method: str, path: str, headers: dict[str, str]) -> int:
    body = {} if method in ("POST", "PUT", "PATCH") else None
    r = await client.request(method, "/api/v1" + path, headers=headers, json=body)
    return r.status_code


@pytest.mark.parametrize("role", ["customer", "agent", "reviewer", "manager", "admin"])
async def test_default_access_matches_today(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]], role: str
) -> None:
    headers = auth_headers(Role(role))
    wrong = []
    for method, path, allowed in ROUTES:
        status = await call(client, method, path, headers)
        if (status != 403) != (role in allowed):
            wrong.append((method, path, status))
    assert wrong == []
