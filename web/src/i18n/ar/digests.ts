/** قاموس الواجهة: شاشة "digests" — ملخصات مجدولة وفورية مع الاستشهادات. */
import type { Dict } from "../types";

export const dict: Dict = {
  // الشريط العلوي
  "digests.subtitle":
    "كل بند يستشهد بمصادره؛ الفترات غير المتغيرة لا يُعاد تحليلها أبداً",
  "digests.newSchedule": "جدول جديد",
  "digests.newScheduleOption": "جدول جديد…",
  "digests.newDaily": "ملخص يومي",
  "digests.newWeekly": "ملخص أسبوعي",
  "digests.lastDay": "ملخص آخر يوم",
  "digests.lastDayHint": "تلخيص آخر 24 ساعة",
  "digests.lastWeek": "ملخص آخر أسبوع",
  "digests.lastWeekHint": "تلخيص آخر 7 أيام",
  "digests.aiRequired": "هيّئ مزوّد ذكاء اصطناعي أولاً",

  // نطاق الطلب الفوري
  "digests.scopeLabel": "نطاق الطلب الفوري (المجموعات):",

  // صفوف الجداول
  "digests.schedules": "الجداول",
  "digests.freqWeekly": "أسبوعي",
  "digests.atHour": "الساعة {h}:00 UTC",
  "digests.scopeGroups": "{n} مجموعات",
  "digests.lastRun": "آخر تشغيل: {date}",
  "digests.scheduleDeleted": "حُذف الجدول",

  // سجل الملخصات
  "digests.emptyTitle": "لا ملخصات بعد",
  "digests.emptyHintAi":
    "أنشئ ملخصاً فورياً (آخر يوم / آخر أسبوع) أو ضع جدولاً — تُنشأ " +
    "الملخصات تلقائياً وتُؤرشف مع استشهاداتها.",
  "digests.emptyHintAiOff":
    "هيّئ مزوّد ذكاء اصطناعي (من الإعدادات) لتفعيل الملخصات.",
  "digests.backAll": "كل الملخصات",
  "digests.deleted": "حُذف الملخص",
  "digests.citations": "الاستشهادات ({n})",
  "digests.deletedFromArchive": "[حُذف من الأرشيف]",
  "digests.scheduled": "مجدول",
  "digests.onDemand": "عند الطلب",
  "digests.queued": "قُيّد إنشاء الملخص في قائمة الانتظار — تابعه في المهام",
  "digests.alreadyQueued": "مهمة ملخص في قائمة الانتظار بالفعل",

  // محرر الجدول
  "digests.newScheduleTitle": "جدول ملخص جديد",
  "digests.schedNote":
    "يُنشأ الملخص تلقائياً حول الساعة التي تختارها (UTC) ويُحفظ مع " +
    "استشهاداته. لا يُعاد إرسال شيء ما دامت الفترة لم تتغير.",
  "digests.frequency": "التكرار",
  "digests.daily": "يومي",
  "digests.weekly": "أسبوعي",
  "digests.hourUtc": "الساعة (UTC)",
  "digests.language": "اللغة",
  "digests.langAuto": "كشف تلقائي",
  "digests.fieldScope": "المجموعات (فارغ = الكل)",
  "digests.create": "إنشاء",
  "digests.scheduleCreated": "أُنشئ الجدول",
};
