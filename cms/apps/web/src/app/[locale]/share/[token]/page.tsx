"use client";

import { useParams } from "next/navigation";
import { ShareTracker } from "@/components/share/share-tracker";

export default function SharePage() {
  const params = useParams<{ token: string }>();
  return <ShareTracker token={params.token} />;
}
