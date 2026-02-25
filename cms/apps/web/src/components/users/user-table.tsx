"use client";

import { MoreHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import type { User } from "@/types/user";

const ROLE_COLORS: Record<string, string> = {
  admin:
    "bg-status-critical/10 text-status-critical border-status-critical/20",
  dispatcher: "bg-interactive/10 text-interactive border-interactive/20",
  editor:
    "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
  viewer: "bg-surface text-foreground-muted border-border",
};

function RoleBadge({ role }: { role: string }) {
  const t = useTranslations("users.roles");
  return (
    <Badge
      variant="outline"
      className={cn("text-xs", ROLE_COLORS[role] ?? "")}
    >
      {t(role)}
    </Badge>
  );
}

function StatusBadge({ isActive }: { isActive: boolean }) {
  const t = useTranslations("users.detail");
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-xs",
        isActive
          ? "bg-status-ontime/10 text-status-ontime border-status-ontime/20"
          : "bg-status-critical/10 text-status-critical border-status-critical/20",
      )}
    >
      {isActive ? t("active") : t("inactive")}
    </Badge>
  );
}

interface UserTableProps {
  users: User[];
  totalItems: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  selectedUser: User | null;
  onSelectUser: (user: User) => void;
  onEditUser: (user: User) => void;
  onDeleteUser: (user: User) => void;
  onResetPassword: (user: User) => void;
  isLoading: boolean;
}

export function UserTable({
  users,
  totalItems,
  page,
  pageSize,
  onPageChange,
  selectedUser,
  onSelectUser,
  onEditUser,
  onDeleteUser,
  onResetPassword,
  isLoading,
}: UserTableProps) {
  const t = useTranslations("users");
  const totalPages = Math.ceil(totalItems / pageSize);

  if (isLoading) {
    return (
      <div className="space-y-2 p-(--spacing-card)">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={`skel-${i}`} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-(--spacing-page)">
        <div className="text-center">
          <p className="text-sm font-medium text-foreground">
            {t("table.noResults")}
          </p>
        </div>
      </div>
    );
  }

  const formatDate = (dateStr: string) => {
    try {
      return new Intl.DateTimeFormat("en-CA").format(new Date(dateStr));
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("table.name")}</TableHead>
              <TableHead>{t("table.email")}</TableHead>
              <TableHead>{t("table.role")}</TableHead>
              <TableHead>{t("table.status")}</TableHead>
              <TableHead className="hidden lg:table-cell">
                {t("table.created")}
              </TableHead>
              <TableHead className="w-10">
                <span className="sr-only">{t("table.actions")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow
                key={user.id}
                className={cn(
                  "cursor-pointer",
                  selectedUser?.id === user.id && "bg-selected-bg",
                )}
                onClick={() => onSelectUser(user)}
              >
                <TableCell className="font-medium">{user.name}</TableCell>
                <TableCell className="text-foreground-muted">
                  {user.email}
                </TableCell>
                <TableCell>
                  <RoleBadge role={user.role} />
                </TableCell>
                <TableCell>
                  <StatusBadge isActive={user.is_active} />
                </TableCell>
                <TableCell className="hidden lg:table-cell text-foreground-muted">
                  {formatDate(user.created_at)}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="size-8 p-0"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreHorizontal className="size-4" />
                        <span className="sr-only">{t("table.actions")}</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          onEditUser(user);
                        }}
                      >
                        {t("actions.edit")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          onResetPassword(user);
                        }}
                      >
                        {t("actions.resetPassword")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteUser(user);
                        }}
                        className="text-status-critical"
                      >
                        {t("actions.delete")}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-end border-t border-border px-(--spacing-card) py-(--spacing-tight)">
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  onClick={() => onPageChange(Math.max(1, page - 1))}
                  aria-disabled={page === 1}
                  className={cn(
                    page === 1 && "pointer-events-none opacity-50",
                  )}
                />
              </PaginationItem>
              {Array.from({ length: totalPages }, (_, i) => (
                <PaginationItem key={i} className="hidden sm:inline-flex">
                  <PaginationLink
                    isActive={i + 1 === page}
                    onClick={() => onPageChange(i + 1)}
                  >
                    {i + 1}
                  </PaginationLink>
                </PaginationItem>
              ))}
              <PaginationItem>
                <PaginationNext
                  onClick={() =>
                    onPageChange(Math.min(totalPages, page + 1))
                  }
                  aria-disabled={page === totalPages}
                  className={cn(
                    page === totalPages && "pointer-events-none opacity-50",
                  )}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      )}
    </div>
  );
}
