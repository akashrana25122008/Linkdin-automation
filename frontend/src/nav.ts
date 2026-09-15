import {
  BarChart3,
  BookOpen,
  CalendarDays,
  FlaskConical,
  LayoutDashboard,
  Megaphone,
  PenSquare,
  Send,
  Settings as SettingsIcon,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  path: string;
  label: string;
  description: string;
  icon: LucideIcon;
  milestone: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    path: "/",
    label: "Overview",
    description: "Workspace at a glance",
    icon: LayoutDashboard,
    milestone: "M3",
  },
  {
    path: "/research",
    label: "Research",
    description: "Topic and signal discovery",
    icon: FlaskConical,
    milestone: "M5",
  },
  {
    path: "/studio",
    label: "Content Studio",
    description: "Write with AI assistance",
    icon: PenSquare,
    milestone: "M4",
  },
  {
    path: "/drafts",
    label: "Drafts",
    description: "Work in progress",
    icon: BookOpen,
    milestone: "M6",
  },
  {
    path: "/calendar",
    label: "Calendar",
    description: "Schedule and plan",
    icon: CalendarDays,
    milestone: "M7",
  },
  {
    path: "/published",
    label: "Published",
    description: "Live LinkedIn posts",
    icon: Send,
    milestone: "M10",
  },
  {
    path: "/analytics",
    label: "Analytics",
    description: "Performance insights",
    icon: BarChart3,
    milestone: "M11",
  },
  {
    path: "/strategy",
    label: "Strategy",
    description: "Brand profile and goals",
    icon: Megaphone,
    milestone: "M8",
  },
  {
    path: "/settings",
    label: "Settings",
    description: "Profile and preferences",
    icon: SettingsIcon,
    milestone: "a later milestone",
  },
];
