"use client";

import { useState, useMemo, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RouteFilters } from "@/components/routes/route-filters";
import { RouteTable } from "@/components/routes/route-table";
import { RouteDetail } from "@/components/routes/route-detail";
import { RouteForm } from "@/components/routes/route-form";
import { DeleteRouteDialog } from "@/components/routes/delete-route-dialog";
import { MOCK_ROUTES } from "@/lib/mock-routes-data";
import type { Route, RouteFormData, RouteType } from "@/types/route";

// Simulated role — in production, read from session
const USER_ROLE: string = "admin";
const IS_READ_ONLY = USER_ROLE === "viewer" || USER_ROLE === "dispatcher";

export default function RoutesPage() {
  const t = useTranslations("routes");

  // Data state
  const [routes, setRoutes] = useState<Route[]>(MOCK_ROUTES);

  // Filter state
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<RouteType | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");

  // UI state
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formInitialData, setFormInitialData] = useState<RouteFormData | undefined>();
  const [formKey, setFormKey] = useState(0);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Route | null>(null);

  // Derived
  const selectedRoute = useMemo(
    () => routes.find((r) => r.id === selectedRouteId) ?? null,
    [routes, selectedRouteId],
  );

  const filtered = useMemo(() => {
    return routes.filter((route) => {
      // Search filter
      if (search) {
        const q = search.toLowerCase();
        const matchesSearch =
          route.shortName.toLowerCase().includes(q) ||
          route.longName.toLowerCase().includes(q) ||
          route.description.toLowerCase().includes(q);
        if (!matchesSearch) return false;
      }
      // Type filter
      if (typeFilter !== null && route.type !== typeFilter) return false;
      // Status filter
      if (statusFilter === "active" && !route.isActive) return false;
      if (statusFilter === "inactive" && route.isActive) return false;
      return true;
    });
  }, [routes, search, typeFilter, statusFilter]);

  // Handlers
  const handleSelectRoute = useCallback(
    (routeId: string) => {
      setSelectedRouteId(routeId);
      setDetailOpen(true);
    },
    [],
  );

  const handleCreate = useCallback(() => {
    setFormMode("create");
    setFormInitialData(undefined);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, []);

  const handleEdit = useCallback((route: Route) => {
    setFormMode("edit");
    setFormInitialData({
      shortName: route.shortName,
      longName: route.longName,
      type: route.type,
      agencyId: route.agencyId,
      color: route.color,
      textColor: route.textColor,
      description: route.description,
      isActive: route.isActive,
    });
    setSelectedRouteId(route.id);
    setDetailOpen(false);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, []);

  const handleDuplicate = useCallback(
    (route: Route) => {
      const now = new Date().toISOString();
      const newRoute: Route = {
        ...route,
        id: `route-dup-${Date.now()}`,
        shortName: `${route.shortName}-copy`,
        createdAt: now,
        updatedAt: now,
      };
      setRoutes((prev) => [...prev, newRoute]);
    },
    [],
  );

  const handleDeleteRequest = useCallback((route: Route) => {
    setDeleteTarget(route);
    setDeleteOpen(true);
  }, []);

  const handleDeleteConfirm = useCallback((routeId: string) => {
    setRoutes((prev) => prev.filter((r) => r.id !== routeId));
    if (selectedRouteId === routeId) {
      setSelectedRouteId(null);
      setDetailOpen(false);
    }
  }, [selectedRouteId]);

  const handleFormSubmit = useCallback(
    (data: RouteFormData) => {
      if (formMode === "create") {
        const now = new Date().toISOString();
        const newRoute: Route = {
          ...data,
          id: `route-new-${Date.now()}`,
          createdAt: now,
          updatedAt: now,
        };
        setRoutes((prev) => [...prev, newRoute]);
      } else if (selectedRouteId) {
        setRoutes((prev) =>
          prev.map((r) =>
            r.id === selectedRouteId
              ? { ...r, ...data, updatedAt: new Date().toISOString() }
              : r,
          ),
        );
      }
    },
    [formMode, selectedRouteId],
  );

  return (
    <div className="flex h-[calc(100vh-var(--spacing-page)*2)] flex-col gap-(--spacing-grid)">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-heading font-semibold text-foreground">
            {t("title")}
          </h1>
          <p className="text-sm text-foreground-muted">{t("description")}</p>
        </div>
        {!IS_READ_ONLY && (
          <Button className="cursor-pointer" onClick={handleCreate}>
            <Plus className="mr-2 size-4" aria-hidden="true" />
            {t("actions.create")}
          </Button>
        )}
      </div>

      {/* 3-panel layout */}
      <div className="flex min-h-0 flex-1 overflow-hidden rounded-lg border border-border">
        {/* Left: Filters */}
        <RouteFilters
          search={search}
          onSearchChange={setSearch}
          typeFilter={typeFilter}
          onTypeFilterChange={setTypeFilter}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          resultCount={filtered.length}
        />

        {/* Center: Table */}
        <RouteTable
          routes={filtered}
          selectedRouteId={selectedRouteId}
          onSelectRoute={handleSelectRoute}
          onEditRoute={handleEdit}
          onDeleteRoute={handleDeleteRequest}
          onDuplicateRoute={handleDuplicate}
          isReadOnly={IS_READ_ONLY}
        />
      </div>

      {/* Right: Detail Sheet (overlay) */}
      <RouteDetail
        route={selectedRoute}
        isOpen={detailOpen}
        onClose={() => setDetailOpen(false)}
        onEdit={handleEdit}
        onDelete={handleDeleteRequest}
        isReadOnly={IS_READ_ONLY}
      />

      {/* Form Sheet */}
      <RouteForm
        key={formKey}
        mode={formMode}
        initialData={formInitialData}
        isOpen={formOpen}
        onClose={() => setFormOpen(false)}
        onSubmit={handleFormSubmit}
      />

      {/* Delete Dialog */}
      <DeleteRouteDialog
        route={deleteTarget}
        isOpen={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
