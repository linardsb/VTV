"use client";

import { useEffect, useState } from "react";

interface LiveTimelineProps {
  startHour?: number;
  endHour?: number;
}

function getMinuteOfDay(): number {
  const now = new Date();
  return now.getHours() * 60 + now.getMinutes();
}

export function LiveTimeline({
  startHour = 6,
  endHour = 22,
}: LiveTimelineProps) {
  const [minuteOfDay, setMinuteOfDay] = useState(getMinuteOfDay);

  useEffect(() => {
    const interval = setInterval(() => {
      setMinuteOfDay(getMinuteOfDay());
    }, 60_000);
    return () => clearInterval(interval);
  }, []);

  const startMinute = startHour * 60;
  const endMinute = endHour * 60;

  // Don't render if outside visible range
  if (minuteOfDay < startMinute || minuteOfDay > endMinute) {
    return null;
  }

  const topPercent =
    ((minuteOfDay - startMinute) / (endMinute - startMinute)) * 100;

  return (
    <div
      className="pointer-events-none absolute right-0 left-0 z-10 flex items-center"
      style={{ top: `${topPercent}%` }}
      aria-hidden="true"
    >
      <div className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-status-critical" />
      <div className="h-[2px] flex-1 bg-status-critical" />
    </div>
  );
}
