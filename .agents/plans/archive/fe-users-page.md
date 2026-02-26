# Plan: Users Page (Admin User Management)

## Feature Metadata
**Feature Type**: New Page (full-stack: backend endpoints + frontend CRUD page)
**Estimated Complexity**: High
**Route**: `/[locale]/(dashboard)/users`
**Auth Required**: Yes
**Allowed Roles**: admin

## Feature Description

Admin-only user management page for the VTV transit operations CMS. Admins can list, create, edit, deactivate, and delete system users across 4 RBAC roles (admin, dispatcher, editor, viewer).

The backend currently has login, logout, token refresh, password reset, and GDPR deletion endpoints — but **no list, get-by-id, create, or update user endpoints**. This plan adds those 4 backend endpoints first, then builds the frontend CRUD page following the established Drivers page pattern.

The page features a searchable table with role/status filters, detail dialog, create/edit form dialog (with password field for creation), reset-password dialog, and delete confirmation dialog.

## Design System

### Master Rules (from MASTER.md)
- Typography: Lexend headings, Source Sans 3 body, 16px+ base
- Spacing: semantic tokens (`--spacing-page`, `--spacing-card`, `--spacing-inline`, `--spacing-grid`)
- Colors: semantic tokens only — no primitive Tailwind colors
- Style: Accessible & Ethical — WCAG compliant, 44x44px touch targets, focus rings

### Page Override
- None — no page override exists in `cms/design-system/vtv/pages/`

### Tokens Used
- Surface: `bg-surface`, `bg-surface-raised`, `bg-background`
- Text: `text-foreground`, `text-foreground-muted`, `text-label-text`
- Interactive: `bg-interactive`, `text-interactive-foreground`
- Status: `text-status-ontime`, `text-status-critical`, `text-status-delayed`
- Border: `border-border`, `border-border-subtle`
- Nav: `bg-nav-active-bg`, `text-nav-active-text`, `text-nav-inactive-text`
- Selected: `bg-selected-bg`
- Spacing: `--spacing-page`, `--spacing-card`, `--spacing-inline`, `--spacing-grid`

## Components Needed

### Existing (shadcn/ui — already installed)
- `Dialog` / `DialogContent` / `DialogHeader` / `DialogTitle` / `DialogDescription` / `DialogFooter` — detail, form, delete, reset-password modals
- `Table` / `TableHeader` / `TableRow` / `TableHead` / `TableCell` / `TableBody` — user list
- `Button` — actions
- `Input` — search, form fields
- `Label` — form labels
- `Select` / `SelectTrigger` / `SelectContent` / `SelectItem` / `SelectValue` — role/status filters and form dropdowns
- `Badge` — role and status indicators
- `Switch` — is_active toggle
- `Skeleton` — loading states
- `Sheet` / `SheetContent` / `SheetHeader` / `SheetTitle` — mobile filters
- `DropdownMenu` / `DropdownMenuTrigger` / `DropdownMenuContent` / `DropdownMenuItem` — row actions
- `Separator` — form section dividers

### New shadcn/ui to Install
- None — all needed components are installed

### Custom Components to Create
- `UserTable` at `cms/apps/web/src/components/users/user-table.tsx`
- `UserFilters` at `cms/apps/web/src/components/users/user-filters.tsx`
- `UserDetail` at `cms/apps/web/src/components/users/user-detail.tsx`
- `UserForm` at `cms/apps/web/src/components/users/user-form.tsx`
- `DeleteUserDialog` at `cms/apps/web/src/components/users/delete-user-dialog.tsx`
- `ResetPasswordDialog` at `cms/apps/web/src/components/users/reset-password-dialog.tsx`

## i18n Keys

### Latvian (`lv.json`) — add under `"users"` key
```json
{
  "users": {
    "title": "Lietotāju pārvaldība",
    "description": "Pārvaldiet sistēmas lietotājus un piekļuves tiesības",
    "search": "Meklēt lietotājus...",
    "filters": {
      "allRoles": "Visas lomas",
      "admin": "Administrators",
      "dispatcher": "Dispečers",
      "editor": "Redaktors",
      "viewer": "Skatītājs",
      "allStatuses": "Visi statusi",
      "active": "Aktīvs",
      "inactive": "Neaktīvs",
      "role": "Loma",
      "status": "Statuss"
    },
    "table": {
      "name": "Vārds",
      "email": "E-pasts",
      "role": "Loma",
      "status": "Statuss",
      "created": "Izveidots",
      "actions": "Darbības",
      "noResults": "Lietotāji nav atrasti",
      "showing": "Rāda {from}-{to} no {total}"
    },
    "detail": {
      "title": "Lietotāja informācija",
      "name": "Vārds",
      "email": "E-pasts",
      "role": "Loma",
      "status": "Statuss",
      "createdAt": "Izveidots",
      "updatedAt": "Atjaunināts",
      "active": "Aktīvs",
      "inactive": "Neaktīvs"
    },
    "roles": {
      "admin": "Administrators",
      "dispatcher": "Dispečers",
      "editor": "Redaktors",
      "viewer": "Skatītājs"
    },
    "form": {
      "createTitle": "Pievienot lietotāju",
      "editTitle": "Rediģēt lietotāju",
      "name": "Vārds",
      "namePlaceholder": "piem., Jānis Bērziņš",
      "email": "E-pasts",
      "emailPlaceholder": "piem., janis@vtv.lv",
      "password": "Parole",
      "passwordPlaceholder": "Vismaz 10 rakstzīmes",
      "passwordHelp": "Vismaz 10 rakstzīmes, 1 lielais burts, 1 mazais burts, 1 cipars",
      "role": "Loma",
      "selectRole": "Izvēlieties lomu",
      "isActive": "Aktīvs",
      "required": "Obligāts lauks"
    },
    "actions": {
      "create": "Pievienot lietotāju",
      "edit": "Rediģēt",
      "delete": "Dzēst",
      "save": "Saglabāt",
      "cancel": "Atcelt",
      "resetPassword": "Atjaunot paroli"
    },
    "delete": {
      "title": "Dzēst lietotāju",
      "confirmation": "Vai tiešām vēlaties dzēst lietotāju \"{name}\"?",
      "warning": "Šī darbība ir neatgriezeniska. Lietotājs tiks neatgriezeniski dzēsts no sistēmas.",
      "confirm": "Dzēst",
      "cancel": "Atcelt"
    },
    "resetPassword": {
      "title": "Atjaunot paroli",
      "description": "Iestatiet jaunu paroli lietotājam \"{name}\"",
      "newPassword": "Jaunā parole",
      "placeholder": "Vismaz 10 rakstzīmes",
      "help": "Vismaz 10 rakstzīmes, 1 lielais burts, 1 mazais burts, 1 cipars",
      "confirm": "Atjaunot",
      "cancel": "Atcelt"
    },
    "toast": {
      "created": "Lietotājs veiksmīgi izveidots",
      "updated": "Lietotājs veiksmīgi atjaunināts",
      "deleted": "Lietotājs veiksmīgi dzēsts",
      "passwordReset": "Parole veiksmīgi atjaunota",
      "createError": "Neizdevās izveidot lietotāju",
      "updateError": "Neizdevās atjaunināt lietotāju",
      "deleteError": "Neizdevās dzēst lietotāju",
      "resetError": "Neizdevās atjaunot paroli"
    },
    "mobile": {
      "showFilters": "Filtri"
    }
  }
}
```

### English (`en.json`) — add under `"users"` key
```json
{
  "users": {
    "title": "User Management",
    "description": "Manage system users and access permissions",
    "search": "Search users...",
    "filters": {
      "allRoles": "All Roles",
      "admin": "Admin",
      "dispatcher": "Dispatcher",
      "editor": "Editor",
      "viewer": "Viewer",
      "allStatuses": "All Statuses",
      "active": "Active",
      "inactive": "Inactive",
      "role": "Role",
      "status": "Status"
    },
    "table": {
      "name": "Name",
      "email": "Email",
      "role": "Role",
      "status": "Status",
      "created": "Created",
      "actions": "Actions",
      "noResults": "No users found",
      "showing": "Showing {from}-{to} of {total}"
    },
    "detail": {
      "title": "User Information",
      "name": "Name",
      "email": "Email",
      "role": "Role",
      "status": "Status",
      "createdAt": "Created",
      "updatedAt": "Updated",
      "active": "Active",
      "inactive": "Inactive"
    },
    "roles": {
      "admin": "Admin",
      "dispatcher": "Dispatcher",
      "editor": "Editor",
      "viewer": "Viewer"
    },
    "form": {
      "createTitle": "Add User",
      "editTitle": "Edit User",
      "name": "Name",
      "namePlaceholder": "e.g., John Smith",
      "email": "Email",
      "emailPlaceholder": "e.g., john@vtv.lv",
      "password": "Password",
      "passwordPlaceholder": "At least 10 characters",
      "passwordHelp": "Min 10 chars, 1 uppercase, 1 lowercase, 1 digit",
      "role": "Role",
      "selectRole": "Select role",
      "isActive": "Active",
      "required": "Required field"
    },
    "actions": {
      "create": "Add User",
      "edit": "Edit",
      "delete": "Delete",
      "save": "Save",
      "cancel": "Cancel",
      "resetPassword": "Reset Password"
    },
    "delete": {
      "title": "Delete User",
      "confirmation": "Are you sure you want to delete user \"{name}\"?",
      "warning": "This action cannot be undone. The user will be permanently removed from the system.",
      "confirm": "Delete",
      "cancel": "Cancel"
    },
    "resetPassword": {
      "title": "Reset Password",
      "description": "Set a new password for \"{name}\"",
      "newPassword": "New Password",
      "placeholder": "At least 10 characters",
      "help": "Min 10 chars, 1 uppercase, 1 lowercase, 1 digit",
      "confirm": "Reset",
      "cancel": "Cancel"
    },
    "toast": {
      "created": "User created successfully",
      "updated": "User updated successfully",
      "deleted": "User deleted successfully",
      "passwordReset": "Password reset successfully",
      "createError": "Failed to create user",
      "updateError": "Failed to update user",
      "deleteError": "Failed to delete user",
      "resetError": "Failed to reset password"
    },
    "mobile": {
      "showFilters": "Filters"
    }
  }
}
```

## Data Fetching

### Backend Endpoints (4 new + 2 existing)

**New endpoints to create (admin-only, under `/api/v1/auth`):**
| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/api/v1/auth/users` | List users (paginated, filtered) | Query: page, page_size, search, role, is_active | `PaginatedResponse[UserResponse]` |
| GET | `/api/v1/auth/users/{user_id}` | Get single user | Path: user_id | `UserResponse` |
| POST | `/api/v1/auth/users` | Create user | Body: email, name, password, role | `UserResponse` |
| PATCH | `/api/v1/auth/users/{user_id}` | Update user | Body: name?, email?, role?, is_active? | `UserResponse` |

**Existing endpoints to use:**
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/auth/reset-password` | Reset user password (body: `{ user_id, new_password }`) |
| DELETE | `/api/v1/auth/users/{user_id}` | Delete user (GDPR) |

### Server/Client Boundary
- Page component is `"use client"` — all data fetching via `authFetch` from client hooks
- Session gate: `useEffect` guarded by `status === "authenticated"`
- `authFetch` handles dual-context (server/client) internally

### Loading States
- `Skeleton` components in table rows during initial load
- Button loading states during form submissions

## RBAC Integration

**Middleware**: Already configured — `/users` is in the matcher pattern and `ROLE_PERMISSIONS.admin` includes `/users`. No changes needed to `middleware.ts`.

**Role permissions (from middleware.ts line 6):**
```typescript
admin: ["/routes", "/stops", "/schedules", "/drivers", "/gtfs", "/users", "/chat", "/documents"],
```

## Sidebar Navigation

**Current state**: `app-sidebar.tsx` line 27 has `{ key: "users", href: "/users", enabled: false }`.
**Action**: Change `enabled: false` → `enabled: true`.
**Label key**: `nav.users` — already exists in both `lv.json` ("Lietotāji") and `en.json` ("Users").
**Position**: Between GTFS and Documents (already positioned correctly).

## Relevant Files

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Backend Pattern Files (for new endpoints)
- `app/auth/routes.py` — Existing auth routes (add new endpoints here)
- `app/auth/schemas.py` — Existing schemas (add CreateUserRequest, UpdateUserRequest)
- `app/auth/service.py` — Existing service (add list, get, create, update methods)
- `app/auth/repository.py` — Existing repository (add list method)
- `app/auth/dependencies.py` — `require_role("admin")` dependency
- `app/auth/exceptions.py` — Auth-specific exceptions
- `app/shared/schemas.py` — `PaginatedResponse[T]`, `PaginationParams`
- `app/shared/utils.py` — `escape_like()` for ILIKE search
- `app/drivers/repository.py` — Reference for list+count pattern with search/filters

### Frontend Pattern Files
- `cms/apps/web/src/app/[locale]/(dashboard)/drivers/page.tsx` — CRUD page pattern
- `cms/apps/web/src/components/drivers/driver-table.tsx` — Table with pagination + actions
- `cms/apps/web/src/components/drivers/driver-filters.tsx` — Desktop sidebar + mobile sheet filters
- `cms/apps/web/src/components/drivers/driver-detail.tsx` — Read-only detail dialog
- `cms/apps/web/src/components/drivers/driver-form.tsx` — Create/edit form dialog
- `cms/apps/web/src/components/drivers/delete-driver-dialog.tsx` — Delete confirmation dialog
- `cms/apps/web/src/lib/drivers-client.ts` — API client pattern
- `cms/apps/web/src/types/driver.ts` — TypeScript interface pattern

### Files to Modify
- `app/auth/repository.py` — Add `list` and `count_filtered` methods
- `app/auth/schemas.py` — Add `CreateUserRequest`, `UpdateUserRequest`, `UserDetailResponse`
- `app/auth/service.py` — Add `list_users`, `get_user`, `create_user`, `update_user` methods
- `app/auth/routes.py` — Add 4 new endpoints
- `cms/apps/web/messages/lv.json` — Add `users` i18n keys
- `cms/apps/web/messages/en.json` — Add `users` i18n keys
- `cms/apps/web/src/components/app-sidebar.tsx` — Enable users nav item

## Design System Color Rules

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400` | `text-foreground-muted` |
| `text-white` (on colored bg) | `text-interactive-foreground` |
| `bg-blue-600` | `bg-interactive` |
| `bg-red-500` | `bg-status-critical` or destructive button variant |
| `bg-red-50` | `bg-status-critical/10` |
| `bg-green-500` | `bg-status-ontime` |
| `bg-gray-100` | `bg-surface` |
| `border-gray-200` | `border-border` |

## React 19 Coding Rules

- **No `setState` in `useEffect`** — use `key` prop on form component to force remount
- **No component definitions inside components** — extract `DetailRow`, `FilterContent` etc. to module scope
- **No `Math.random()` in render** — use `useId()` if needed
- **Hook ordering** — `useState`/`useCallback`/`useMemo` declarations before dependent hooks

## TypeScript Security Rules

- Never `as` cast API response fields without runtime validation
- Role fields from API: validate against known roles array before using
- Passwords: client-side validation mirrors backend rules (10+ chars, 1 upper, 1 lower, 1 digit)

---

## Step by Step Tasks

### Task 1: Backend — Add list and count methods to UserRepository
**File:** `app/auth/repository.py` (modify)
**Action:** UPDATE

Add two methods following the `app/drivers/repository.py` pattern:

```python
async def list(
    self,
    *,
    offset: int = 0,
    limit: int = 20,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> list[User]:
```
- Import `func, or_` from sqlalchemy and `escape_like` from `app.shared.utils`
- Search across `User.name` and `User.email` using ILIKE with `escape_like()`
- Filter by `role` and `is_active` when provided
- Order by `User.name` ascending
- Apply `.offset(offset).limit(limit)`

```python
async def count_filtered(
    self,
    *,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> int:
```
- Mirror the same filter logic as `list()` but return count

**Per-task validation:**
- `make types` passes (mypy + pyright)
- `make lint` passes

---

### Task 2: Backend — Add user management schemas
**File:** `app/auth/schemas.py` (modify)
**Action:** UPDATE

Add schemas after existing `UserResponse`:

```python
class UserDetailResponse(BaseModel):
    """User detail with timestamps."""
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {"from_attributes": True}

class CreateUserRequest(BaseModel):
    """Admin creates a new user."""
    email: EmailStr
    name: str
    password: str
    role: str = "viewer"

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {"admin", "dispatcher", "editor", "viewer"}
        if v not in valid:
            msg = f"Role must be one of: {', '.join(sorted(valid))}"
            raise ValueError(msg)
        return v

class UpdateUserRequest(BaseModel):
    """Admin updates user fields."""
    name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valid = {"admin", "dispatcher", "editor", "viewer"}
        if v not in valid:
            msg = f"Role must be one of: {', '.join(sorted(valid))}"
            raise ValueError(msg)
        return v
```

Add `import datetime` at top of file if not present.

**Per-task validation:**
- `make types` passes
- `make lint` passes

---

### Task 3: Backend — Add user management service methods
**File:** `app/auth/service.py` (modify)
**Action:** UPDATE

Add 4 methods to `AuthService` class:

```python
async def list_users(
    self,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> PaginatedResponse[UserDetailResponse]:
```
- Import `PaginatedResponse` from `app.shared.schemas`
- Import `UserDetailResponse` from `app.auth.schemas`
- Calculate offset: `(page - 1) * page_size`
- Call `self.repo.list(...)` and `self.repo.count_filtered(...)`
- Return `PaginatedResponse(items=[UserDetailResponse.model_validate(u) for u in users], total=total, page=page, page_size=page_size)`

```python
async def get_user(self, user_id: int) -> UserDetailResponse:
```
- Call `self.repo.find_by_id(user_id)`
- Raise `InvalidCredentialsError("User not found")` if None
- Return `UserDetailResponse.model_validate(user)`

```python
async def create_user(self, data: CreateUserRequest) -> UserDetailResponse:
```
- Import `CreateUserRequest` from `app.auth.schemas`
- Import `DomainValidationError` from `app.core.exceptions`
- Check email uniqueness: `self.repo.find_by_email(data.email)` — raise `DomainValidationError("Email already in use")` if found
- Create `User(email=data.email, name=data.name, hashed_password=self.hash_password(data.password), role=data.role)`
- Call `self.repo.create(user)`
- Log `auth.user_created`
- Return `UserDetailResponse.model_validate(user)`

```python
async def update_user(self, user_id: int, data: UpdateUserRequest) -> UserDetailResponse:
```
- Import `UpdateUserRequest` from `app.auth.schemas`
- Call `self.repo.find_by_id(user_id)` — raise if not found
- If `data.email` is set and differs from current, check uniqueness
- Apply non-None fields: `for field, value in data.model_dump(exclude_unset=True).items(): setattr(user, field, value)`
- Call `self.repo.update(user)` (which commits + refreshes)
- Log `auth.user_updated`
- Return `UserDetailResponse.model_validate(user)`

**Per-task validation:**
- `make types` passes
- `make lint` passes

---

### Task 4: Backend — Add CRUD route endpoints
**File:** `app/auth/routes.py` (modify)
**Action:** UPDATE

Add imports at top: `from fastapi import Query` and new schema imports (`CreateUserRequest`, `UpdateUserRequest`, `UserDetailResponse`).
Add `from app.shared.schemas import PaginatedResponse`.

Add 4 new endpoints **before** the existing `delete_user_data` endpoint:

```python
@router.get("/users", response_model=PaginatedResponse[UserDetailResponse])
@limiter.limit("30/minute")
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
    _admin: User = Depends(require_role("admin")),
    service: AuthService = Depends(get_service),
) -> PaginatedResponse[UserDetailResponse]:
    """List all users with pagination and filters (admin only)."""
    _ = request
    return await service.list_users(
        page=page, page_size=page_size, search=search, role=role, is_active=is_active,
    )

@router.get("/users/{user_id}", response_model=UserDetailResponse)
@limiter.limit("30/minute")
async def get_user(
    request: Request,
    user_id: int,
    _admin: User = Depends(require_role("admin")),
    service: AuthService = Depends(get_service),
) -> UserDetailResponse:
    """Get a single user by ID (admin only)."""
    _ = request
    return await service.get_user(user_id)

@router.post("/users", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_user(
    request: Request,
    body: CreateUserRequest,
    _admin: User = Depends(require_role("admin")),
    service: AuthService = Depends(get_service),
) -> UserDetailResponse:
    """Create a new user (admin only)."""
    _ = request
    return await service.create_user(body)

@router.patch("/users/{user_id}", response_model=UserDetailResponse)
@limiter.limit("10/minute")
async def update_user(
    request: Request,
    user_id: int,
    body: UpdateUserRequest,
    _admin: User = Depends(require_role("admin")),
    service: AuthService = Depends(get_service),
) -> UserDetailResponse:
    """Update a user's profile (admin only)."""
    _ = request
    return await service.update_user(user_id, body)
```

**IMPORTANT**: The new `GET /users` and `GET /users/{user_id}` routes must be placed **before** the existing `DELETE /users/{user_id}` route so FastAPI resolves them correctly. Add `# noqa: B008` to all `Depends()` calls.

**Per-task validation:**
- `make types` passes
- `make lint` passes
- `make test` passes (existing tests still pass)

---

### Task 5: Frontend — Add Latvian i18n keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add the complete `"users"` block from the i18n section above. Insert it after the `"gtfs"` block (to match sidebar ordering). Ensure valid JSON comma separation.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 6: Frontend — Add English i18n keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add the complete `"users"` block from the i18n section above. Insert it after the `"gtfs"` block. Ensure keys exactly mirror the Latvian structure.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 7: Frontend — Create user types
**File:** `cms/apps/web/src/types/user.ts` (create)
**Action:** CREATE

```typescript
export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  name: string;
  password: string;
  role: string;
}

export interface UserUpdate {
  name?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

export interface PaginatedUsers {
  items: User[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 8: Frontend — Create API client
**File:** `cms/apps/web/src/lib/users-client.ts` (create)
**Action:** CREATE

Follow the `drivers-client.ts` pattern exactly:
- `const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8123";`
- `const API_PREFIX = "/api/v1/auth";`
- Custom `UsersApiError` class with `status` property
- Generic `handleResponse<T>` helper
- Functions: `fetchUsers(params)`, `fetchUser(id)`, `createUser(data)`, `updateUser(id, data)`, `deleteUser(id)`, `resetUserPassword(userId, newPassword)`
- Use `authFetch` from `@/lib/auth-fetch` for all requests
- `fetchUsers` builds `URLSearchParams` from: `page`, `page_size`, `search`, `role`, `is_active`
- `resetUserPassword` calls `POST ${BASE_URL}${API_PREFIX}/reset-password` with body `{ user_id: userId, new_password: newPassword }`
- `deleteUser` calls `DELETE ${BASE_URL}${API_PREFIX}/users/${id}`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Frontend — Create UserTable component
**File:** `cms/apps/web/src/components/users/user-table.tsx` (create)
**Action:** CREATE

Follow `driver-table.tsx` pattern:
- Props: `users`, `isLoading`, `selectedUser`, `onSelectUser`, `onEdit`, `onDelete`, `onResetPassword`, `page`, `totalItems`, `pageSize`, `onPageChange`
- Columns: Name, Email, Role (Badge), Status (Badge), Created (formatted date), Actions (DropdownMenu)
- Role badge color mapping using semantic tokens:
  - admin: `bg-status-critical/10 text-status-critical border-status-critical/20`
  - dispatcher: `bg-interactive/10 text-interactive border-interactive/20`
  - editor: `bg-status-delayed/10 text-status-delayed border-status-delayed/20`
  - viewer: `bg-surface text-foreground-muted border-border`
- Status badge: active = `bg-status-ontime/10 text-status-ontime`, inactive = `bg-status-critical/10 text-status-critical`
- Loading skeleton (5 rows)
- Empty state with `text-foreground-muted`
- Selected row highlight with `bg-selected-bg`
- Actions dropdown: Edit, Reset Password, Delete (destructive text)
- Pagination at bottom using the same pattern as driver-table

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Frontend — Create UserFilters component
**File:** `cms/apps/web/src/components/users/user-filters.tsx` (create)
**Action:** CREATE

Follow `driver-filters.tsx` pattern:
- Props: `search`, `onSearchChange`, `roleFilter`, `onRoleFilterChange`, `statusFilter`, `onStatusFilterChange`, `totalCount`, `asSheet?`, `sheetOpen?`, `onSheetOpenChange?`
- Extract `FilterContent` to module scope (React 19 rule)
- Desktop: `<aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface p-(--spacing-card)">`
- Mobile: `<Sheet>` wrapper
- Search: `<Input>` with search icon
- Role filter: `<Select>` with All Roles + 4 role options
- Status filter: `<Select>` with All Statuses + Active/Inactive
- Result count display

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 11: Frontend — Create UserDetail component
**File:** `cms/apps/web/src/components/users/user-detail.tsx` (create)
**Action:** CREATE

Follow `driver-detail.tsx` pattern:
- Props: `user`, `open`, `onOpenChange`, `onEdit`, `onDelete`, `onResetPassword`
- Uses `Dialog` (NOT Sheet) — centered modal, `sm:max-w-md`
- Must include `DialogDescription` for Radix accessibility
- Extract `DetailRow` helper to module scope
- Sections: User Info (name, email, role badge, status badge), Metadata (created_at, updated_at)
- Footer: Edit, Reset Password, Delete buttons
- Date formatting helper for created_at/updated_at

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 12: Frontend — Create UserForm component
**File:** `cms/apps/web/src/components/users/user-form.tsx` (create)
**Action:** CREATE

Follow `driver-form.tsx` pattern:
- Props: `user?` (null for create), `open`, `onOpenChange`, `onSubmit`
- Uses `Dialog` — centered modal, `sm:max-w-lg`
- Must include `DialogDescription` for Radix accessibility
- Fields: name (Input), email (Input), password (Input, type="password" — **create mode only**), role (Select with 4 options)
- Edit mode: show `isActive` Switch, hide password field
- Create mode: show password field, hide isActive toggle
- Derive `isEdit` from `!!user` prop
- Client-side validation: required fields (name, email, role; password required in create mode)
- Password validation hint: "Min 10 chars, 1 uppercase, 1 lowercase, 1 digit"
- Diff-based submit for edit mode (only send changed fields)
- Footer: Cancel + Save buttons
- **No `setState` in useEffect** — component remounts via `key` prop from parent

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 13: Frontend — Create DeleteUserDialog component
**File:** `cms/apps/web/src/components/users/delete-user-dialog.tsx` (create)
**Action:** CREATE

Follow `delete-driver-dialog.tsx` pattern exactly:
- Props: `user`, `open`, `onOpenChange`, `onConfirm`
- AlertTriangle icon in `bg-status-critical/10` circle
- Interpolated name in confirmation message
- Warning text in `text-foreground-muted`
- Cancel (outline) + Delete (destructive) buttons

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 14: Frontend — Create ResetPasswordDialog component
**File:** `cms/apps/web/src/components/users/reset-password-dialog.tsx` (create)
**Action:** CREATE

New component (no direct analogue — combine delete dialog structure with form input):
- Props: `user`, `open`, `onOpenChange`, `onConfirm: (newPassword: string) => void`
- Uses `Dialog` — centered modal
- Must include `DialogDescription`
- Single password input (`type="password"`) with help text
- Client-side validation: min 10 chars, 1 uppercase, 1 lowercase, 1 digit
- Show validation error text below input when invalid
- Cancel + Reset buttons
- Clear password field when dialog opens (component remounts via key prop)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 15: Frontend — Create Users page component
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/users/page.tsx` (create)
**Action:** CREATE

Follow `drivers/page.tsx` pattern exactly:
- `"use client"` directive
- Session gate: `const { data: session, status } = useSession();` — guard `useEffect` with `status !== "authenticated"`
- State management:
  - Data: `users`, `totalItems`, `page`, `isLoading`
  - Filters: `search`, `debouncedSearch` (300ms debounce), `roleFilter`, `statusFilter`
  - UI: `selectedUser`, `detailOpen`, `formOpen`, `formMode`, `formKey`, `deleteOpen`, `deleteTarget`, `resetOpen`, `resetTarget`, `filterSheetOpen`
- `PAGE_SIZE = 20`
- `loadUsers` wrapped in `useCallback` — calls `fetchUsers(...)` from users-client
- Debounced search resets page to 1
- Handlers: `handleSelectUser`, `handleCreateClick` (increment formKey), `handleEditUser`, `handleDeleteUser`, `handleResetPassword`, `handleFormSubmit`, `handleDeleteConfirm`, `handleResetConfirm`
- Layout: header with title + Create button, desktop filters sidebar + table, mobile filter sheet
- Render all dialogs: `UserDetail`, `UserForm` (with key={formKey}), `DeleteUserDialog`, `ResetPasswordDialog`
- Toast notifications via `sonner` for success/error

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 16: Frontend — Enable sidebar nav entry
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify)
**Action:** UPDATE

Change line 27 from:
```typescript
{ key: "users", href: "/users", enabled: false },
```
to:
```typescript
{ key: "users", href: "/users", enabled: true },
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

## Final Validation (3-Level Pyramid)

### Backend
```bash
make lint && make types && make test
```

### Frontend
**Level 1: TypeScript**
```bash
cd cms && pnpm --filter @vtv/web type-check
```

**Level 2: Lint**
```bash
cd cms && pnpm --filter @vtv/web lint
```

**Level 3: Build**
```bash
cd cms && pnpm --filter @vtv/web build
```

**Success definition:** All levels exit code 0, zero errors AND zero warnings.

## Post-Implementation Checks

- [ ] Backend: `GET /api/v1/auth/users` returns paginated list (admin only)
- [ ] Backend: `POST /api/v1/auth/users` creates user with hashed password
- [ ] Backend: `PATCH /api/v1/auth/users/{id}` updates user fields
- [ ] Backend: Non-admin gets 403 on all user management endpoints
- [ ] Frontend: Page renders at `/lv/users` and `/en/users`
- [ ] Frontend: i18n keys present in both lv.json and en.json
- [ ] Frontend: Sidebar nav link shows "Lietotāji" / "Users" and navigates correctly
- [ ] Frontend: Non-admin users redirected to /unauthorized
- [ ] Frontend: Table loads users, search works, role/status filters work
- [ ] Frontend: Create user form validates password requirements
- [ ] Frontend: Edit user form shows current values, submits only changed fields
- [ ] Frontend: Delete confirmation dialog works, user removed from table
- [ ] Frontend: Reset password dialog validates password, calls existing endpoint
- [ ] Frontend: No hardcoded colors — all styling uses semantic tokens
- [ ] Frontend: All interactive elements have ARIA labels
- [ ] Frontend: Design tokens from tokens.css used (no arbitrary Tailwind values)

## Security Checklist
- [ ] All new endpoints use `require_role("admin")` dependency
- [ ] Password hashed with bcrypt before storage (never stored in plain text)
- [ ] Email uniqueness enforced at service layer (DomainValidationError)
- [ ] Admin cannot delete own account (existing check in delete_user_data)
- [ ] No user role names exposed in error messages (generic "Insufficient permissions")
- [ ] Password complexity validated both client-side (UX) and server-side (security)
- [ ] No `dangerouslySetInnerHTML` used
- [ ] All API calls use `authFetch` (bearer token via httpOnly cookie)

## Acceptance Criteria

This feature is complete when:
- [ ] 4 new backend endpoints pass type checking + lint + tests
- [ ] Page accessible at `/{locale}/users` for admin users only
- [ ] RBAC enforced — non-admin roles redirected to /unauthorized
- [ ] Both languages have complete translations
- [ ] Full CRUD: list, create, edit, delete users
- [ ] Password reset works via dedicated dialog
- [ ] Design system rules followed (semantic tokens only)
- [ ] All validation levels pass (type-check, lint, build, backend tests)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`
