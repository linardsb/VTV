export type EventPriority = "high" | "medium" | "low";
export type EventCategory = "maintenance" | "route-change" | "driver-shift" | "service-alert";

export interface OperationalEvent {
  id: number;
  title: string;
  description: string | null;
  start_datetime: string;
  end_datetime: string;
  priority: EventPriority;
  category: EventCategory;
  created_at: string;
  updated_at: string;
}

export interface EventCreate {
  title: string;
  description?: string | null;
  start_datetime: string;
  end_datetime: string;
  priority?: EventPriority;
  category?: EventCategory;
}

export interface EventUpdate {
  title?: string;
  description?: string | null;
  start_datetime?: string;
  end_datetime?: string;
  priority?: EventPriority;
  category?: EventCategory;
}

export interface PaginatedEvents {
  items: OperationalEvent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
