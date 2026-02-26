export type EventPriority = "high" | "medium" | "low";
export type EventCategory = "maintenance" | "route-change" | "driver-shift" | "service-alert";
export type TransportType = "bus" | "trolleybus" | "tram";
export type GoalItemType = "route" | "training" | "note" | "checklist";

export interface GoalItem {
  text: string;
  completed: boolean;
  item_type: GoalItemType;
}

export interface EventGoals {
  items: GoalItem[];
  route_id: number | null;
  transport_type: TransportType | null;
  vehicle_id: string | null;
}

export interface OperationalEvent {
  id: number;
  title: string;
  description: string | null;
  start_datetime: string;
  end_datetime: string;
  priority: EventPriority;
  category: EventCategory;
  goals: EventGoals | null;
  driver_id: number | null;
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
  goals?: EventGoals | null;
  driver_id?: number | null;
}

export interface EventUpdate {
  title?: string;
  description?: string | null;
  start_datetime?: string;
  end_datetime?: string;
  priority?: EventPriority;
  category?: EventCategory;
  goals?: EventGoals | null;
  driver_id?: number | null;
}

export interface PaginatedEvents {
  items: OperationalEvent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
