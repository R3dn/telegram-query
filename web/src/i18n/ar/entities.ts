/** قاموس الواجهة: شاشة "entities" (الجهات). */
import type { Dict } from "../types";

export const dict: Dict = {
  // رأس الشاشة
  "entities.subtitle":
    "علامات تجارية ومنتجات ومؤسسات وأماكن - وليس أفراداً أبداً",
  "entities.searchPlaceholder": "ابحث في الجهات…",
  "entities.sort.recent": "النشاط الأحدث",
  "entities.sort.mentions": "الأكثر ذكراً",
  "entities.add.submit": "إضافة",

  // اكتشاف الجهات بالذكاء الاصطناعي
  "entities.autoLabel":
    "اكتشاف الجهات الجديدة بالذكاء الاصطناعي (اختياري؛ يعمل تدريجياً " +
    "بعد كل مزامنة، مع تخزين مؤقت حسب المحتوى)",
  "entities.toast.autoOn":
    "اكتشاف الجهات بالذكاء الاصطناعي مفعّل - تُكتشف الجهات الجديدة " +
    "تدريجياً بعد كل مزامنة (مع تخزين مؤقت، ويمكن إيقافه في أي وقت)",
  "entities.toast.autoOff":
    "اكتشاف الجهات بالذكاء الاصطناعي متوقف - تستمر المطابقة وفق دليل الجهات الحالي",

  // صفوف الجهات
  "entities.row.mention": "{n} إشارة",
  "entities.row.mentions": "{n} إشارات",
  "entities.row.recent": "{n} هذا الأسبوع",
  "entities.row.lastSeen": "آخر ظهور {d}",
  "entities.hideHint": "إخفاء من الاستكشاف (مع الاحتفاظ بالسجل)",
  "entities.toast.hidden": "تم إخفاء الجهة",

  // صفحة التفاصيل
  "entities.backToList": "كل الجهات",
  "entities.detail.stats": "{n} إشارة · {g} مجموعة",
  "entities.detail.groupChip": "{n} إشارة",
  "entities.hideFromDiscovery": "إخفاء من الاستكشاف",
  "entities.mergeInto": "دمج هذه الجهة في…",
  "entities.mergeHint": "انقل إشارات هذه الجهة وأسماءها البديلة إلى جهة أخرى",
  "entities.toast.merged": "تم دمج الجهتين - نُقلت الإشارات والأسماء البديلة",
  "entities.toast.deleted": "حُذفت الجهة (الإشارات كانت مجرد مراجع)",
  "entities.detail.mentions": "الإشارات",
  "entities.detail.noMentions": "لا إشارات بعد - تتراكم بعد كل مزامنة.",
  "entities.detail.older": "+{n} إشارة أقدم",

  // الحالة الفارغة ونموذج الإضافة
  "entities.empty.title": "لا جهات بعد",
  "entities.empty.hintSynced":
    "أضف العلامات التجارية والمنتجات يدوياً، أو استوردها من العروض " +
    "المستخرجة (خيار «إعادة بناء البيانات» في شاشة الاستكشاف)، أو فعّل " +
    "اكتشاف الجهات بالذكاء الاصطناعي لتظهر تدريجياً بعد كل مزامنة.",
  "entities.empty.hintNoSync": "زامن مجموعاتك أولاً.",
  "entities.add.title": "جهة جديدة",
  "entities.add.namePlaceholder": "الاسم، مثلاً: GadgetHub",
  "entities.add.aliasesPlaceholder": "الأسماء البديلة (مفصولة بفواصل)",
  "entities.toast.added": "تمت إضافة الجهة",
};
