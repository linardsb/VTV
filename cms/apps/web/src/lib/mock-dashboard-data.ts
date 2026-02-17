import type { CalendarEvent, MetricData } from "@/types/dashboard";

export const MOCK_METRICS: MetricData[] = [
  {
    title: "Active Vehicles",
    value: "342",
    delta: "+12",
    deltaType: "positive",
    subtitle: "Compared to 330 last month",
  },
  {
    title: "On-Time Performance",
    value: "94.2%",
    delta: "+2.1%",
    deltaType: "positive",
    subtitle: "Compared to 92.1% last month",
  },
  {
    title: "Delayed Routes",
    value: "3",
    delta: "+1",
    deltaType: "negative",
    subtitle: "Compared to 2 last month",
  },
  {
    title: "Fleet Utilization",
    value: "87%",
    delta: "+5%",
    deltaType: "positive",
    subtitle: "Compared to 82% last month",
  },
];

function getWeekDay(offset: number): Date {
  const now = new Date();
  const day = now.getDay();
  // Get Monday of current week
  const monday = new Date(now);
  monday.setDate(now.getDate() - ((day + 6) % 7));
  // Offset from Monday
  const target = new Date(monday);
  target.setDate(monday.getDate() + offset);
  return target;
}

function setTime(date: Date, hours: number, minutes: number): Date {
  const d = new Date(date);
  d.setHours(hours, minutes, 0, 0);
  return d;
}

export const MOCK_EVENTS: CalendarEvent[] = [
  {
    id: "evt-1",
    title: "eventTitles.busFleetInspection",
    start: setTime(getWeekDay(0), 8, 0),
    end: setTime(getWeekDay(0), 10, 0),
    priority: "high",
    category: "maintenance",
    description: "eventDescriptions.busFleetInspection",
  },
  {
    id: "evt-2",
    title: "eventTitles.route15Detour",
    start: setTime(getWeekDay(0), 14, 0),
    end: setTime(getWeekDay(0), 16, 0),
    priority: "medium",
    category: "route-change",
    description: "eventDescriptions.route15Detour",
  },
  {
    id: "evt-3",
    title: "eventTitles.morningShiftHandover",
    start: setTime(getWeekDay(1), 6, 0),
    end: setTime(getWeekDay(1), 7, 0),
    priority: "low",
    category: "driver-shift",
  },
  {
    id: "evt-4",
    title: "eventTitles.trolleybusLineMaintenance",
    start: setTime(getWeekDay(1), 10, 0),
    end: setTime(getWeekDay(1), 13, 0),
    priority: "high",
    category: "maintenance",
    description: "eventDescriptions.trolleybusLineMaintenance",
  },
  {
    id: "evt-5",
    title: "eventTitles.serviceAlertIceWarning",
    start: setTime(getWeekDay(2), 7, 0),
    end: setTime(getWeekDay(2), 9, 0),
    priority: "high",
    category: "service-alert",
    description: "eventDescriptions.serviceAlertIceWarning",
  },
  {
    id: "evt-6",
    title: "eventTitles.route22ScheduleChange",
    start: setTime(getWeekDay(2), 12, 0),
    end: setTime(getWeekDay(2), 14, 0),
    priority: "medium",
    category: "route-change",
  },
  {
    id: "evt-7",
    title: "eventTitles.eveningShiftCoverage",
    start: setTime(getWeekDay(3), 16, 0),
    end: setTime(getWeekDay(3), 18, 0),
    priority: "low",
    category: "driver-shift",
  },
  {
    id: "evt-8",
    title: "eventTitles.depotAMaintenanceWindow",
    start: setTime(getWeekDay(4), 9, 0),
    end: setTime(getWeekDay(4), 12, 0),
    priority: "medium",
    category: "maintenance",
    description: "eventDescriptions.depotAMaintenanceWindow",
  },
  {
    id: "evt-9",
    title: "eventTitles.weekendScheduleActivation",
    start: setTime(getWeekDay(5), 8, 0),
    end: setTime(getWeekDay(5), 10, 0),
    priority: "low",
    category: "route-change",
  },
  {
    id: "evt-10",
    title: "eventTitles.emergencyDrill",
    start: setTime(getWeekDay(3), 10, 0),
    end: setTime(getWeekDay(3), 11, 30),
    priority: "high",
    category: "service-alert",
    description: "eventDescriptions.emergencyDrill",
  },
];
