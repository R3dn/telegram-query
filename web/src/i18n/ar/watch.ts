/** قاموس الواجهة: شاشة "watch" — قوائم المراقبة وصندوق التنبيهات. */
import type { Dict } from "../types";

export const dict: Dict = {
  // شريط قوائم المراقبة
  "watch.subtitle":
    "مراقبة كلمات مفتاحية — بلا حاجة إلى ذكاء اصطناعي، وتُقيَّم بعد كل مزامنة",
  "watch.checkNow": "تحقّق الآن",
  "watch.checkNowHint": "تقييم كل ما هو أحدث من العلامة المائية",
  "watch.checkBackfill": "تحقّق عن آخر 7 أيام",
  "watch.checkBackfillHint": "إعادة فحص الأيام الأخيرة لهذه المرة فقط",
  "watch.newList": "قائمة مراقبة جديدة",
  "watch.checkedNew": "{n} تنبيهات جديدة — {u} غير مقروءة",
  "watch.checkedNone": "لا تطابقات جديدة",

  // بطاقات قوائم المراقبة
  "watch.emptyTitle": "لا قوائم مراقبة بعد",
  "watch.emptyHint":
    "أنشئ قائمة مراقبة بكلمات مفتاحية (مثل kubernetes أو عرض أو " +
    "SAVE20) وسينبّهك تيليجرام كويري عند ذكرها في المجموعات المتتبعة " +
    "— بلا بحث يدوي ولا استدعاءات ذكاء اصطناعي.",
  "watch.badgeNew": "{n} جديدة",
  "watch.paused": "متوقفة",
  "watch.pause": "إيقاف",
  "watch.resume": "استئناف",
  "watch.edit": "تعديل",
  "watch.deleted": "حُذفت قائمة المراقبة",

  // محرر قائمة المراقبة
  "watch.editTitle": "تعديل قائمة المراقبة",
  "watch.modalNote":
    "تُطابق المصطلحات كما يفعل البحث (مع تطبيع العربية). المطابقة " +
    "حتمية وتجري بعد كل مزامنة — رسائلك لا تُرسل أبداً إلى مزوّد " +
    "ذكاء اصطناعي لأجل ذلك.",
  "watch.fieldName": "الاسم",
  "watch.phName": "مثلاً: وظائف k8s · عروض التقنية",
  "watch.fieldTerms": "المصطلحات (مفصولة بفواصل)",
  "watch.phTerms": "kubernetes, k8s, وظائف",
  "watch.fieldExcludes": "مصطلحات الاستثناء (اختياري)",
  "watch.phExcludes": "pricing",
  "watch.fieldScope": "المجموعات (فارغ = الكل)",
  "watch.needNameAndTerm": "الاسم ومصطلح واحد على الأقل مطلوبان",
  "watch.created": "أُنشئت قائمة المراقبة",
  "watch.updated": "حُدِّثت قائمة المراقبة",

  // صندوق التنبيهات
  "watch.tabNew": "الجديدة",
  "watch.tabRead": "المقروءة",
  "watch.tabArchived": "المؤرشفة",
  "watch.refresh": "تحديث",
  "watch.emptyNew": "لا تنبيهات جديدة",
  "watch.emptyRead": "لا تنبيهات مقروءة",
  "watch.emptyArchived": "لا تنبيهات مؤرشفة",
  "watch.emptyNewHint":
    "تطابقات قوائم المراقبة تصل هنا بعد كل مزامنة مباشرة. لا جديد " +
    "منذ آخر زيارة.",
  "watch.emptyOtherHint": "لا شيء هنا بعد.",
  "watch.markRead": "تحديد كمقروء",
  "watch.archive": "أرشفة",
  "watch.jump": "انتقال",
  "watch.matchedTerm": "المطابق: «{term}»",
  "watch.jumpFailed": "تعذر فتح الرسالة الأصلية",
};
