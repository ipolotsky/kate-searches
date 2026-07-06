import { Badge } from "flowbite-react";

interface ScoreBadgeProps {
  score: number;
  label?: string;
}

type BadgeColor = "success" | "warning" | "gray";

export const scoreColor = (score: number): BadgeColor => {
  if (score >= 70) {
    return "success";
  }
  if (score >= 50) {
    return "warning";
  }
  return "gray";
};

export const ScoreBadge: React.FC<ScoreBadgeProps> = (props) => (
  <Badge color={scoreColor(props.score)}>
    {props.label != null ? `${props.label} ${props.score}` : props.score}
  </Badge>
);
