/** قاموس الواجهة: شاشة "deals". */
import type { Dict } from "../types";

export const dict: Dict = {
  // شريط الأدوات
  "deals.searchPlaceholder": "ابحث في العروض…",
  "deals.filterStatus": "تصفية حسب الحالة",
  "deals.anyStatus": "أي حالة",
  "deals.filterCategory": "تصفية حسب الفئة",
  "deals.anyCategory": "أي فئة",
  "deals.filterGroup": "تصفية حسب المجموعة",
  "deals.sort": "الترتيب",
  "deals.sortDiscount": "أكبر خصم",
  "deals.sortPrice": "أقل سعر",
  "deals.exportMd": "تصدير .md",
  "deals.exportJson": ".json",
  "deals.exported": "تم التصدير",
  "deals.extract": "استخراج العروض",
  "deals.extractHint": "تحليل الأرشيف للبحث عن العروض",
  "deals.aiNeeded": "اضبط مزوّد الذكاء الاصطناعي أولاً",

  // صف الاستخراج التلقائي
  "deals.autoHint": "بعد كل مزامنة، تحليل الرسائل الجديدة فقط",
  "deals.autoLabel": "استخراج الرسائل الجديدة تلقائياً بعد كل مزامنة",
  "deals.autoOn": "الاستخراج التلقائي مفعّل",
  "deals.autoOff": "الاستخراج التلقائي متوقف",
  "deals.autoNote": "يرسل الاستخراج مقتطفات الرسائل المرشحة إلى {host}",

  // حالات الفراغ
  "deals.noMatch": "لا عروض مطابقة",
  "deals.empty": "لا عروض بعد",
  "deals.tryDifferent": "جرّب عوامل تصفية مختلفة.",
  "deals.emptyAiHint":
    "شغّل «استخراج العروض» لتحليل مجموعاتك والبحث عن العروض، أو أضف عرضاً " +
    "يدوياً. الاستخراج يرسل الرسائل المرشحة فقط — وليس أرشيفك كله أبداً.",
  "deals.emptyNoAiHint":
    "اضبط مزوّد ذكاء اصطناعي (الإعدادات) لتمكين الاستخراج، أو أضف العروض يدوياً.",

  // بطاقة العرض
  "deals.badgeConfirmed": "مؤكَّد",
  "deals.confirmed": "تم التأكيد",
  "deals.sourceOne": "مصدر واحد",
  "deals.sourceMany": "{n} مصادر",
  "deals.confidence": "الثقة: {label}",
  "deals.who": "لمن: {v}",
  "deals.where": "الموقع: {v}",
  "deals.from": "من: {v}",
  "deals.sourcesLabel": "المصادر ({n})",
  "deals.deletedFromArchive": "[حُذف من الأرشيف]",
  "deals.dismiss": "تجاهل",
  "deals.dismissed": "تم التجاهل",
  "deals.correctExpiry": "تصحيح تاريخ الانتهاء",
  "deals.saveExpiry": "حفظ تاريخ الانتهاء",
  "deals.expiryUpdated": "تم تحديث تاريخ الانتهاء",
  "deals.deleted": "تم حذف العرض",

  // نافذة الاستخراج
  "deals.extractNote":
    "يحلل الرسائل المطابقة لكلمات العروض ضمن النطاق المحدد، ثم يرسل " +
    "المرشحات فقط (على دفعات) إلى مزوّد الذكاء الاصطناعي لديك. تُدمج العروض " +
    "الموجودة بحسب هويتها — ولا تُكرَّر أبداً. تظهر المهمة وتقدّمها في «المهام».",
  "deals.scope": "النطاق",
  "deals.noGroups": "لا مجموعات متابعة بعد.",
  "deals.dateRange": "الفترة الزمنية (اختياري)",
  "deals.startExtract": "بدء الاستخراج",
  "deals.extractQueued": "الاستخراج في قائمة الانتظار — تابع تقدّمه في «المهام»",
  "deals.extractAlreadyQueued": "الاستخراج في قائمة الانتظار بالفعل",
};
