"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { Plus, Filter } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";
import { UserFilters } from "@/components/users/user-filters";
import { UserTable } from "@/components/users/user-table";
import { UserDetail } from "@/components/users/user-detail";
import { UserForm } from "@/components/users/user-form";
import { DeleteUserDialog } from "@/components/users/delete-user-dialog";
import { ResetPasswordDialog } from "@/components/users/reset-password-dialog";
import {
  fetchUsers,
  createUser,
  updateUser,
  deleteUser,
  resetUserPassword,
} from "@/lib/users-client";
import type { User, UserCreate, UserUpdate } from "@/types/user";

const PAGE_SIZE = 20;

export default function UsersPage() {
  const t = useTranslations("users");
  const isMobile = useIsMobile();
  const { status } = useSession();

  // Data state
  const [users, setUsers] = useState<User[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  // UI state
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formKey, setFormKey] = useState(0);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<User | null>(null);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Load data
  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    try {
      const isActiveParam =
        statusFilter === "active"
          ? true
          : statusFilter === "inactive"
            ? false
            : undefined;
      const result = await fetchUsers({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        role: roleFilter !== "all" ? roleFilter : undefined,
        is_active: isActiveParam,
      });
      setUsers(result.items);
      setTotalItems(result.total);
    } catch (e) {
      console.warn("[users] Failed to load:", e);
      toast.error(t("toast.loadError"));
    } finally {
      setIsLoading(false);
    }
  }, [page, debouncedSearch, roleFilter, statusFilter, t]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadUsers();
  }, [loadUsers, status]);

  // Handlers
  const handleSelectUser = (user: User) => {
    setSelectedUser(user);
    setDetailOpen(true);
  };

  const handleCreateClick = () => {
    setSelectedUser(null);
    setFormMode("create");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
  };

  const handleEditUser = (user: User) => {
    setSelectedUser(user);
    setFormMode("edit");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
    setDetailOpen(false);
  };

  const handleDeleteUser = (user: User) => {
    setDeleteTarget(user);
    setDeleteOpen(true);
    setDetailOpen(false);
  };

  const handleResetPassword = (user: User) => {
    setResetTarget(user);
    setResetOpen(true);
    setDetailOpen(false);
  };

  const handleFormSubmit = async (data: UserCreate | UserUpdate) => {
    try {
      if (formMode === "create") {
        await createUser(data as UserCreate);
        toast.success(t("toast.created"));
      } else if (selectedUser) {
        await updateUser(selectedUser.id, data as UserUpdate);
        toast.success(t("toast.updated"));
      }
      setFormOpen(false);
      void loadUsers();
    } catch {
      toast.error(
        formMode === "create"
          ? t("toast.createError")
          : t("toast.updateError"),
      );
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteUser(deleteTarget.id);
      toast.success(t("toast.deleted"));
      setDeleteTarget(null);
      if (selectedUser?.id === deleteTarget.id) {
        setSelectedUser(null);
        setDetailOpen(false);
      }
      void loadUsers();
    } catch {
      toast.error(t("toast.deleteError"));
    }
  };

  const handleResetConfirm = async (newPassword: string) => {
    if (!resetTarget) return;
    try {
      await resetUserPassword(resetTarget.id, newPassword);
      toast.success(t("toast.passwordReset"));
      setResetTarget(null);
    } catch {
      toast.error(t("toast.resetError"));
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-(--spacing-page) py-(--spacing-card)">
        <div>
          <h1 className="text-lg font-heading font-semibold text-foreground">
            {t("title")}
          </h1>
          <p className="text-sm text-foreground-muted">{t("description")}</p>
        </div>
        <div className="flex items-center gap-2">
          {isMobile && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setFilterSheetOpen(true)}
            >
              <Filter className="mr-1 size-4" />
              {t("mobile.showFilters")}
            </Button>
          )}
          <Button size="sm" onClick={handleCreateClick}>
            <Plus className="mr-1 size-4" />
            {t("actions.create")}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Desktop filters */}
        {!isMobile && (
          <UserFilters
            search={search}
            onSearchChange={setSearch}
            roleFilter={roleFilter}
            onRoleFilterChange={(v) => {
              setRoleFilter(v);
              setPage(1);
            }}
            statusFilter={statusFilter}
            onStatusFilterChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            resultCount={totalItems}
          />
        )}

        {/* Mobile filter sheet */}
        {isMobile && (
          <UserFilters
            asSheet
            sheetOpen={filterSheetOpen}
            onSheetOpenChange={setFilterSheetOpen}
            search={search}
            onSearchChange={setSearch}
            roleFilter={roleFilter}
            onRoleFilterChange={(v) => {
              setRoleFilter(v);
              setPage(1);
            }}
            statusFilter={statusFilter}
            onStatusFilterChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            resultCount={totalItems}
          />
        )}

        {/* Table */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <UserTable
            users={users}
            totalItems={totalItems}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
            selectedUser={selectedUser}
            onSelectUser={handleSelectUser}
            onEditUser={handleEditUser}
            onDeleteUser={handleDeleteUser}
            onResetPassword={handleResetPassword}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Detail Dialog */}
      <UserDetail
        user={selectedUser}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onEdit={() => {
          if (selectedUser) handleEditUser(selectedUser);
        }}
        onDelete={() => {
          if (selectedUser) handleDeleteUser(selectedUser);
        }}
        onResetPassword={() => {
          if (selectedUser) handleResetPassword(selectedUser);
        }}
      />

      {/* Form Dialog */}
      <UserForm
        key={formKey}
        mode={formMode}
        user={formMode === "edit" ? selectedUser : null}
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleFormSubmit}
      />

      {/* Delete Dialog */}
      <DeleteUserDialog
        user={deleteTarget}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={handleDeleteConfirm}
      />

      {/* Reset Password Dialog */}
      <ResetPasswordDialog
        key={resetTarget?.id ?? "reset"}
        user={resetTarget}
        open={resetOpen}
        onOpenChange={setResetOpen}
        onConfirm={handleResetConfirm}
      />
    </div>
  );
}
