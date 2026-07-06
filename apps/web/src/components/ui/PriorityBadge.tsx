import { Badge } from "flowbite-react";
import type { Priority } from "@/lib/types";

interface PriorityBadgeProps {
  priority: Priority;
}

type BadgeColor = "failure" | "warning" | "info" | "gray";

export const PRIORITY_COLORS: Record<Priority, BadgeColor> = {
  HOT: "failure",
  WARM: "warning",
  COLD: "info",
  DROP: "gray",
};

export const PriorityBadge: React.FC<PriorityBadgeProps> = (props) => (
  <Badge color={PRIORITY_COLORS[props.priority]} className="uppercase">
    {props.priority}
  </Badge>
);
