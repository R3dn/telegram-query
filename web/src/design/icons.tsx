/** Centralized Lucide icon system.
 *
 *  One import point for every icon in the app:
 *    import { Ic } from "../design/icons";
 *    <Ic.Search />              // 16px, 1.75 stroke — consistent everywhere
 *    <Ic.ChevronRight size={14} />
 *
 *  Design rules:
 *  - No emojis in the UI, ever; these SVG icons are the only pictograms.
 *  - Directional icons (arrows, chevrons, reply, external-link, panel
 *    toggles) are auto-mirrored in RTL via the `icon-flip` class —
 *    logical direction for free, no per-call-site RTL branches.
 *  - Sizes: 14 for inline/meta, 16 for controls (default), 18 for view
 *    headers, 20+ for landing/empty states.
 */
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Ban,
  Bell,
  Bookmark,
  BookOpen,
  Calendar,
  CalendarDays,
  ChartColumn,
  ChartLine,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronsUpDown,
  ClipboardList,
  CircleAlert,
  CircleCheck,
  CircleOff,
  CircleX,
  Clock,
  Compass,
  Copy,
  CornerUpLeft,
  Database,
  Dot,
  Download,
  Eye,
  ExternalLink,
  FileDown,
  FileText,
  Filter,
  Flame,
  FolderOpen,
  Globe,
  HelpCircle,
  Hourglass,
  Image as ImageIcon,
  Inbox,
  Info,
  KeyRound,
  Layers,
  Lightbulb,
  Link2,
  ListFilter,
  LoaderCircle,
  LogOut,
  MapPin,
  Maximize2,
  MessageSquare,
  Minus,
  Moon,
  Newspaper,
  NotepadText,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Play,
  Plus,
  Radio,
  RefreshCw,
  Reply,
  RotateCcw,
  Save,
  Scale,
  Search,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Star,
  Sun,
  Tag,
  Target,
  Trash,
  TrendingUp,
  User,
  Users,
  WifiOff,
  X,
  type LucideIcon,
  type LucideProps,
} from "lucide-react";
import { forwardRef, memo, type ForwardedRef } from "react";

type P = Omit<LucideProps, "ref">;

const BASE = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;

/** Icons whose direction must flip in RTL (they point somewhere). */
const DIRECTIONAL = new Set<string>([
  "ArrowRight", "ArrowUpRight", "ChevronLeft", "ChevronRight",
  "CornerUpLeft", "ExternalLink", "PanelRightClose", "PanelRightOpen",
  "Reply", "RotateCcw", "Send", "ArrowDownToLine",
]);

function wrap(name: string, C: LucideIcon) {
  const Ic = forwardRef<SVGSVGElement, P & { className?: string }>(
    (props: P & { className?: string }, ref: ForwardedRef<SVGSVGElement>) => {
      const { className = "", ...rest } = props;
      const flip = DIRECTIONAL.has(name) ? " icon-flip" : "";
      return (
        <C
          ref={ref}
          {...BASE}
          {...rest}
          className={(className + flip).trim()}
        />
      );
    },
  );
  Ic.displayName = `Ic.${name}`;
  return memo(Ic);
}

export const Ic = {
  // navigation / modes
  TrendingUp: wrap("TrendingUp", TrendingUp),
  Search: wrap("Search", Search),
  Users: wrap("Users", Users),
  Sparkles: wrap("Sparkles", Sparkles),
  RefreshCw: wrap("RefreshCw", RefreshCw),
  Star: wrap("Star", Star),
  Bookmark: wrap("Bookmark", Bookmark),
  Tag: wrap("Tag", Tag),
  Scale: wrap("Scale", Scale),
  FileText: wrap("FileText", FileText),
  BookOpen: wrap("BookOpen", BookOpen),
  Eye: wrap("Eye", Eye),
  Bell: wrap("Bell", Bell),
  Newspaper: wrap("Newspaper", Newspaper),
  HelpCircle: wrap("HelpCircle", HelpCircle),
  MapPin: wrap("MapPin", MapPin),
  Compass: wrap("Compass", Compass),

  // UI chrome
  Close: wrap("X", X),
  ChevronLeft: wrap("ChevronLeft", ChevronLeft),
  ChevronRight: wrap("ChevronRight", ChevronRight),
  ChevronDown: wrap("ChevronDown", ChevronDown),
  ChevronUp: wrap("ChevronUp", ChevronUp),
  ChevronsUpDown: wrap("ChevronsUpDown", ChevronsUpDown),
  Plus: wrap("Plus", Plus),
  Minus: wrap("Minus", Minus),
  Check: wrap("Check", Check),
  CircleCheck: wrap("CircleCheck", CircleCheck),
  CircleX: wrap("CircleX", CircleX),
  Copy: wrap("Copy", Copy),
  ExternalLink: wrap("ExternalLink", ExternalLink),
  ArrowRight: wrap("ArrowRight", ArrowRight),
  ArrowUpRight: wrap("ArrowUpRight", ArrowUpRight),
  ArrowDownToLine: wrap("ArrowDownToLine", ArrowDownToLine),
  Reply: wrap("Reply", Reply),
  CornerUpLeft: wrap("CornerUpLeft", CornerUpLeft),
  PanelRightClose: wrap("PanelRightClose", PanelRightClose),
  PanelRightOpen: wrap("PanelRightOpen", PanelRightOpen),
  Maximize2: wrap("Maximize2", Maximize2),
  Link2: wrap("Link2", Link2),

  // actions / objects
  Trash: wrap("Trash", Trash),
  Pencil: wrap("Pencil", Pencil),
  Save: wrap("Save", Save),
  Settings: wrap("Settings", Settings),
  Sun: wrap("Sun", Sun),
  Moon: wrap("Moon", Moon),
  Globe: wrap("Globe", Globe),
  Calendar: wrap("Calendar", Calendar),
  CalendarDays: wrap("CalendarDays", CalendarDays),
  Database: wrap("Database", Database),
  FolderOpen: wrap("FolderOpen", FolderOpen),
  Layers: wrap("Layers", Layers),
  Image: wrap("Image", ImageIcon),
  Play: wrap("Play", Play),
  Sliders: wrap("SlidersHorizontal", SlidersHorizontal),
  ListFilter: wrap("ListFilter", ListFilter),
  LogOut: wrap("LogOut", LogOut),
  Info: wrap("Info", Info),
  CircleAlert: wrap("CircleAlert", CircleAlert),
  Lightbulb: wrap("Lightbulb", Lightbulb),
  Flame: wrap("Flame", Flame),
  Radio: wrap("Radio", Radio),
  ChartColumn: wrap("ChartColumn", ChartColumn),
  ChartLine: wrap("ChartLine", ChartLine),
  MessageSquare: wrap("MessageSquare", MessageSquare),
  User: wrap("User", User),
  ClipboardList: wrap("ClipboardList", ClipboardList),
  ShieldCheck: wrap("ShieldCheck", ShieldCheck),
  Hourglass: wrap("Hourglass", Hourglass),
  Send: wrap("Send", Send),
  KeyRound: wrap("KeyRound", KeyRound),
  WifiOff: wrap("WifiOff", WifiOff),
  Download: wrap("Download", Download),
  FileDown: wrap("FileDown", FileDown),
  Inbox: wrap("Inbox", Inbox),
  Ban: wrap("Ban", Ban),
  CircleOff: wrap("CircleOff", CircleOff),
  NotepadText: wrap("NotepadText", NotepadText),
  Target: wrap("Target", Target),
  Activity: wrap("Activity", Activity),
  Clock: wrap("Clock", Clock),
  RotateCcw: wrap("RotateCcw", RotateCcw),
  Filter: wrap("Filter", Filter),
  Dot: wrap("Dot", Dot),

  /** Spinning loader (busy indicators only — never decorative). */
  Spin: wrap("LoaderCircle", LoaderCircle),
};

export type IconName = keyof typeof Ic;
