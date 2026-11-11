/** قاموس الواجهة: مساحة الأبحاث (الملخصات). */
import type { Dict } from "../types";

export const dict: Dict = {
  "research.needsAi": "الأبحاث تحتاج مزوّد ذكاء اصطناعي",
  "research.needsAiHint":
    "فعّل AI_API_KEY في الإعدادات لتوليد ملخصات بحثية مُقتبسة من الأدلة. " +
    "كل شيء يبقى محلياً - تُرسل المقتطفات المسترجعة فقط إلى مزوّدك.",
  "research.placeholder":
    "سؤال بحثي… مثال: لخّص كل ما يتعلق بالترحيل إلى Kubernetes · " +
    "ما كل النقاشات حول الترقية؟",
  "research.dateScope": "النطاق الزمني",
  "research.scope.all": "كل الفترات",
  "research.scope.30": "آخر 30 يوماً",
  "research.scope.90": "آخر 90 يوماً",
  "research.scope.custom": "مخصص…",
  "research.submit": "ابحث",
  "research.working": "جارٍ العمل…",
  "research.queued": "أُضيف البحث إلى قائمة المهام - تابع التقدم في المهام",
  "research.briefs": "الملخصات",
  "research.noBriefs": "لا ملخصات بعد - اطرح سؤالك الأول في الأعلى.",
  "research.nNew": "{n} جديد",
  "research.groupsInScope": "المجموعات ضمن النطاق",
  "research.toggleGroup": "تضمين المجموعة في النطاق أو استثناؤها",
  "research.desk": "مكتب أبحاثك",
  "research.deskHint":
    "اطرح سؤالاً عن مجموعاتك. تصبح الإجابة ملخصاً محفوظاً مُقتبساً يمكنك " +
    "إعادة تشغيله أسبوعياً - وسيخبرك متى ظهرت رسائل جديدة ذات صلة.",
  "research.generating": "جارٍ التوليد…",
  "research.generatingHint":
    "يجري بحث ملخصك. تابع التقدم المباشر في لوحة المهام؛ تُحدَّث هذه " +
    "الصفحة تلقائياً.",
  "research.rerun": "إعادة التشغيل",
  "research.rerunQueued": "أُضيفت إعادة التشغيل - نسخة جديدة في الطريق",
  "research.alreadyRunning": "يعمل بالفعل",
  "research.exported": "تم التصدير",
  "research.deleted": "حُذف الملخص",
  "research.exportMd": "تصدير ‎.md",
  "research.exportJson": "‎.json",
  "research.delete": "حذف",
  "research.generated": "وُلّد في {date} · {model}",
  "research.staleBadge": "{n} رسالة جديدة منذ ذلك الحين",
  "research.staleBadgeHint": "ظهرت رسائل جديدة مطابقة للنطاق بعد هذه النسخة",
  "research.citations": "الاستشهادات ({n}) - كل عبارة تُنسب إلى هنا",
  "research.notes": "ملاحظاتك",
  "research.notesPlaceholder": "ملاحظاتك الشخصية عن هذا الملخص (تبقى محلية)…",
  "research.saveNotes": "حفظ الملاحظات",
  "research.notesSaved": "تم حفظ الملاحظات",
  "research.couldNotOpen": "تعذر فتح الرسالة الأصلية",
};
