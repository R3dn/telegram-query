/** قاموس الواجهة: مساحة التصفح (شريط البحث، شريط التصفية، التدفق). */
import type { Dict } from "../types";

export const dict: Dict = {
  // شريط البحث
  "search.placeholder": "ابحث في الرسائل…  (اضغط /)",
  "search.activePlaceholder": "بحث نشط - Enter لإعادة التشغيل، Esc للمسح",
  "search.backToBrowse": "العودة للتصفح",
  "search.recent": "أحدث عمليات البحث",

  // شريط التصفية
  "filter.browse": "تصفح",
  "filter.search": "بحث",
  "filter.allTime": "كل الفترات",
  "filter.today": "اليوم",
  "filter.days": "{n} أيام",
  "filter.custom": "فترة مخصصة",
  "filter.anySender": "أي مرسل",
  "filter.anyType": "أي نوع",
  "filter.withImages": "بصور",
  "filter.textOnly": "نص فقط",
  "filter.newestFirst": "الأحدث أولاً",
  "filter.oldestFirst": "الأقدم أولاً",
  "filter.starred": "المميزة",
  "filter.starredHint": "إظهار الرسائل المحفوظة فقط",
  "filter.save": "حفظ البحث",
  "filter.saveHint": "احفظ هذا البحث وعوامله باسم محدد",
  "filter.moreOnScroll": "المزيد عند التمرير",
  "filter.chip.from": "من {date}",
  "filter.chip.sender": "مرسل: {name}",
  "filter.chip.images": "بصور",
  "filter.chip.text": "نص فقط",
  "filter.chip.oldest": "الأقدم أولاً",
  "filter.chip.starred": "مميزة",
  "filter.chip.groups": "{n} مجموعة",
  "filter.allGroups": "كل المجموعات",
  "filter.saveTitle": "حفظ البحث",
  "filter.saveNote":
    "يحفظ الاستعلام والمجموعات المختارة وعوامل التصفية - لا صفوف النتائج. " +
    "يمكنك تشغيله في أي وقت للتنفيذ من جديد على الأرشيف المباشر.",
  "filter.savePlaceholder": "اسم، مثلاً: أروع العروض / best deals",
  "filter.savedToast": "تم حفظ «{name}»",

  // التدفق
  "feed.marked": "تم الحفظ",
  "feed.unmarked": "أُزيل من المحفوظات",
  "feed.markHint": "احفظ هذه الرسالة",
  "feed.unmarkHint": "إزالة من المحفوظات",
  "feed.edited": "معدّلة",
  "feed.hasImage": "تحتوي صورة",
  "feed.unknown": "مجهول",
  "feed.noResults": "لا نتائج",
  "feed.noResultsHint":
    "لا شيء يطابق «{q}» مع عوامل التصفية الحالية. جرّب صياغة " +
    "أخرى أو عوامل تصفية أقل أو تهجئات بديلة.",
  "feed.archiveEmpty": "أرشيفك فارغ",
  "feed.archiveEmptyHint":
    "أضف بعض المجموعات وشغّل أول مزامنة لتبدأ ببناء أرشيف قابل " +
    "للبحث لرسائل تيليجرام.",
  "feed.noMatch": "لا رسائل مطابقة",
  "feed.noMatchHint":
    "لا رسائل تطابق عوامل التصفية الحالية. وسّع نطاق التاريخ " +
    "أو امسح أحد العوامل.",
  "feed.searchPrompt": "ابحث في أرشيفك",
  "feed.searchPromptHint":
    "اكتب في الأعلى واضغط Enter. افصل الكلمات البديلة بـ | - " +
    "مثلاً:  offer|عرض",
  "feed.loadingOlder": "جارٍ تحميل الرسائل الأقدم…",
  "feed.loadOlder": "تحميل رسائل أقدم",
  "feed.showingNewest":
    "تُعرض أحدث {n} رسالة — ضيّق عوامل التصفية لاستكشاف تاريخ أعمق",
  "feed.jumpLatest": "الانتقال إلى الأحدث",
  "feed.loadFailed": "فشل التحميل: {msg}",
};
