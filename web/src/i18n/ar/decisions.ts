/** قاموس الواجهة: شاشة "decisions". */
import type { Dict } from "../types";

export const dict: Dict = {
  // شريط الأدوات
  "decisions.searchPlaceholder": "ابحث في القرارات…",
  "decisions.filterStatus": "تصفية حسب الحالة",
  "decisions.anyStatus": "أي حالة",
  "decisions.filterKind": "تصفية حسب النوع",
  "decisions.anyKind": "أي نوع",
  "decisions.filterGroup": "تصفية حسب المجموعة",
  "decisions.sort": "الترتيب",
  "decisions.sortDue": "الأقرب استحقاقاً",
  "decisions.sortConfidence": "الأعلى ثقة",
  "decisions.checkFollowups": "فحص المتابعات",
  "decisions.checkFollowupsHint":
    "فحص حتمي بالكلمات المفتاحية — يعمل أيضاً بعد كل مزامنة",
  "decisions.exportMd": "تصدير .md",
  "decisions.exportJson": ".json",
  "decisions.exported": "تم التصدير",
  "decisions.extract": "استخراج القرارات",
  "decisions.extractHint": "تحليل الأرشيف للبحث عن القرارات والالتزامات",
  "decisions.aiNeeded": "اضبط مزوّد الذكاء الاصطناعي أولاً",

  // شريط المراقبة
  "decisions.openLabel": "مفتوحة",
  "decisions.nOverdue": "{n} متأخرة",
  "decisions.showOverdue": "إظهار القرارات المتأخرة",
  "decisions.nDueSoon": "{n} تستحق قريباً",
  "decisions.dueSoonHint": "تستحق خلال 7 أيام",
  "decisions.nWithFollowups": "{n} عليها متابعات",
  "decisions.followupsHint": "قرارات ناقشتها رسائل أحدث",
  "decisions.followupsNote": "تعمل فحوصات المتابعات بعد كل مزامنة",

  // صف الاستخراج التلقائي
  "decisions.autoHint": "بعد كل مزامنة، تحليل الرسائل الجديدة فقط",
  "decisions.autoLabel": "استخراج الرسائل الجديدة تلقائياً بعد كل مزامنة",
  "decisions.autoOn": "الاستخراج التلقائي مفعّل",
  "decisions.autoOff": "الاستخراج التلقائي متوقف",
  "decisions.autoNote": "يرسل الاستخراج مقتطفات الرسائل المرشحة إلى {host}",

  // حالات الفراغ
  "decisions.noMatch": "لا قرارات مطابقة",
  "decisions.empty": "لا قرارات بعد",
  "decisions.tryDifferent": "جرّب عوامل تصفية مختلفة.",
  "decisions.emptyAiHint":
    "شغّل «استخراج القرارات» لتحليل مجموعاتك والبحث عن القرارات " +
    "والالتزامات والخطط، أو أضف قراراً يدوياً. الاستخراج يرسل الرسائل " +
    "المرشحة فقط — وليس أرشيفك كله أبداً.",
  "decisions.emptyNoAiHint":
    "اضبط مزوّد ذكاء اصطناعي (الإعدادات) لتمكين الاستخراج، أو أضف القرارات يدوياً.",

  // بطاقة القرار
  "decisions.badgeConfirmed": "مؤكَّد",
  "decisions.confirmed": "تم التأكيد",
  "decisions.followupOne": "متابعة واحدة",
  "decisions.followupMany": "{n} متابعات",
  "decisions.followupsTitle": "{n} رسالة أحدث تناقش هذا القرار",
  "decisions.dueSoon": "تستحق قريباً",
  "decisions.sourceOne": "مصدر واحد",
  "decisions.sourceMany": "{n} مصادر",
  "decisions.confidence": "الثقة: {label}",
  "decisions.sourcesLabel": "المصادر ({n})",
  "decisions.deletedFromArchive": "[حُذف من الأرشيف]",
  "decisions.followupsLabel": "المتابعات ({n}) — رسائل أحدث عن هذا القرار",
  "decisions.dismiss": "تجاهل",
  "decisions.dismissed": "تم التجاهل",
  "decisions.markCompleted": "تحديد كمكتمل",
  "decisions.markedCompleted": "تم تحديد القرار كمكتمل",
  "decisions.correctOwner": "تصحيح المسؤول",
  "decisions.ownerPlaceholder": "المسؤول…",
  "decisions.saveOwner": "حفظ المسؤول",
  "decisions.ownerUpdated": "تم تحديث المسؤول",
  "decisions.correctDue": "تصحيح تاريخ الاستحقاق",
  "decisions.saveDue": "حفظ تاريخ الاستحقاق",
  "decisions.dueUpdated": "تم تحديث تاريخ الاستحقاق",
  "decisions.deleted": "تم حذف القرار",
  "decisions.followupsFound": "عُثر على {n} متابعة جديدة",
  "decisions.noNewFollowups": "لا متابعات جديدة",

  // نافذة الاستخراج
  "decisions.extractNote":
    "يحلل الرسائل المطابقة لكلمات القرارات/الالتزامات ضمن النطاق المحدد، " +
    "ثم يرسل المرشحات فقط (على دفعات) إلى مزوّد الذكاء الاصطناعي لديك. " +
    "تُدمج القرارات الموجودة بحسب هويتها — ولا تُكرَّر أبداً. تظهر المهمة " +
    "وتقدّمها في «المهام».",
  "decisions.scope": "النطاق",
  "decisions.noGroups": "لا مجموعات متابعة بعد.",
  "decisions.dateRange": "الفترة الزمنية (اختياري)",
  "decisions.startExtract": "بدء الاستخراج",
  "decisions.extractQueued": "الاستخراج في قائمة الانتظار — تابع تقدّمه في «المهام»",
  "decisions.extractAlreadyQueued": "الاستخراج في قائمة الانتظار بالفعل",
};
