/** قاموس الواجهة: شاشة "discover" (الاستكشاف). */
import type { Dict } from "../types";

export const dict: Dict = {
  // رأس الشاشة
  "discover.subtitle":
    "موثوق ومباشر - يُحسب من أرشيفك، دون الحاجة إلى أي ذكاء اصطناعي",
  "discover.window.last": "آخر {n} أيام",
  "discover.rebuild.button": "إعادة بناء البيانات",
  "discover.rebuild.title":
    "إعادة بناء بيانات الاستكشاف كاملة من الأرشيف (تظهر كمهمة في المهام)",
  "discover.rebuild.queued":
    "أُضيفت إعادة بناء الاستكشاف إلى قائمة الانتظار - تابعها في المهام",
  "discover.rebuild.alreadyQueued": "توجد مهمة استكشاف في قائمة الانتظار بالفعل",

  // نطاق المجموعات
  "discover.scope.label": "النطاق:",
  "discover.scope.one": "{n} مجموعة",
  "discover.scope.many": "{n} مجموعات",
  "discover.scope.clearHint": "(امسح الاختيار لعرض جميع المجموعات)",

  // أرشيف فارغ
  "discover.empty.title": "لا شيء لاستكشافه بعد",
  "discover.empty.hint":
    "زامن مجموعاتك أولاً - تظهر المواضيع الرائجة والقصص المشتركة بين " +
    "المجموعات والأسئلة بلا إجابة هنا تلقائياً بعد كل مزامنة.",
  "discover.toast.openOriginalFailed": "تعذّر فتح الرسالة الأصلية",

  // المواضيع الرائجة
  "discover.trending.title": "مواضيع رائجة",
  "discover.trending.note":
    "الحجم الحديث مقابل الفترة السابقة - انقر للانتقال إلى الرسائل",
  "discover.trending.empty": "لم يبرز أي موضوع خلال آخر {n} أيام.",
  "discover.trending.openTitle": "فتح الرسائل المطابقة في التدفق",
  "discover.trending.openSample": "فتح الرسالة النموذجية",
  "discover.trending.badgeTitle": "الحديث مقابل الفترة السابقة",
  "discover.trending.new": "جديد",
  "discover.trending.oneMsg": "{n} رسالة",
  "discover.trending.msgs": "{n} رسائل",
  "discover.trending.oneGroup": "{n} مجموعة",
  "discover.trending.groups": "{n} مجموعات",

  // الخط الزمني للموضوع
  "discover.timeline.button": "الخط الزمني",
  "discover.timeline.badge": "الخط الزمني للموضوع",
  "discover.timeline.analyzing": "جارٍ تحليل الرسائل…",
  "discover.timeline.sources": "المصادر ({n})",
  "discover.toast.citationMissing": "لا توجد رسالة مطابقة للإشارة [{n}]",

  // القصص عبر المجموعات
  "discover.stories.title": "قصص عبر المجموعات",
  "discover.stories.note": "المنشور نفسه مُعاد توجيهه عبر مجتمعاتك",
  "discover.stories.empty": "لا عمليات إعادة توجيه بين المجموعات خلال آخر {n} أيام.",
  "discover.stories.badge": "{g} مجموعات · {n} نسخة",

  // الأسئلة المفتوحة
  "discover.questions.title": "أسئلة بلا إجابة",
  "discover.questions.titleCount": "أسئلة بلا إجابة ({n})",
  "discover.questions.note":
    "أسئلة دون أي رد - أجب عن أحدها، أو دع الأسئلة الشائعة تجيب عنه",
  "discover.questions.scan": "فحص الرسائل الأخيرة",
  "discover.questions.scanNote":
    "يعيد فحص آخر 30 يوماً؛ الحالات التي تحددها يدوياً لا تُستبدل أبداً",
  "discover.questions.empty": "لا أسئلة مفتوحة - المجتمعات تجيب بسرعة.",
  "discover.questions.open": "فتح",
  "discover.questions.markAnswered": "تمت الإجابة",
  "discover.questions.ignore": "تجاهل",
  "discover.questions.noResponse": "لا يظهر أي رد",
  "discover.questions.faqMatch": "توجد إجابة معتمدة من الأسئلة الشائعة مطابقة",
  "discover.toast.scanned": "تم الفحص - {n} سؤال جديد مفتوح",
  "discover.toast.answered": "تم تعليم السؤال كمُجاب",
  "discover.toast.ignored": "تم تجاهل السؤال",

  // نشاط المجموعات
  "discover.activity.title": "نشاط المجموعات (30 يوماً)",
  "discover.activity.note":
    "إجماليات فقط - لا يوفر هذا المنتج أي تحليلات على مستوى الأعضاء",
  "discover.activity.empty": "لا رسائل خلال آخر 30 يوماً.",
  "discover.activity.toggleTitle": "تضمين هذه المجموعة في النطاق أو إزالتها",
  "discover.activity.stats": "{n} رسالة · {p} يومياً",
  "discover.activity.more": "+{n} مجموعات أخرى",
};
