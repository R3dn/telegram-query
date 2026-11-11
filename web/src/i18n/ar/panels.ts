/** قاموس الواجهة: اللوحة اليمنى (التفاصيل، اسأل الذكاء، المحادثة). */
import type { Dict } from "../types";

export const dict: Dict = {
  // لوحة التفاصيل
  "details.emptyHint": "حدد رسالة من التدفق لتظهر تفاصيلها هنا.",
  "details.group": "المجموعة",
  "details.date": "التاريخ",
  "details.sender": "المرسل",
  "details.id": "المعرّف",
  "details.edited": "معدّلة",
  "details.yes": "نعم",
  "details.media": "وسائط",
  "details.mediaNote": "صورة (غير مخزنة محلياً)",
  "details.noText": "[بلا نص / وسائط فقط]",
  "details.noteTitle": "ملاحظة خاصة",
  "details.bookmarked": "محفوظة",
  "details.bookmark": "حفظ",
  "details.notePlaceholder":
    "ملاحظتك (عربي/إنجليزي، تبقى على هذا الجهاز، ولا تُرسل للذكاء أبداً)…",
  "details.noteSave": "حفظ الملاحظة",
  "details.noteSaved": "تم حفظ الملاحظة",
  "details.noteSaving": "جارٍ الحفظ…",
  "details.noteInBookmarks": "تظهر في المحفوظات",
  "details.noteStarsHint": "الحفظ يميّز الرسالة بنجمة",
  "details.copyFailed": "فشل النسخ",
  "details.linkCopied": "تم نسخ رابط الرسالة",
  "details.copyLink": "نسخ رابط الرسالة",
  "details.noLinkHint":
    "المجموعات العامة والسوبر جروب لها روابط لكل رسالة؛ المجموعات " +
    "الأساسية لا. لا نختلق روابط أبداً.",
  "details.noLink": "لا يوجد رابط تيليجرام لهذه المحادثة",
  "details.bySender": "رسائل هذا المرسل",
  "details.filterBySender": "جارٍ التصفية حسب المرسل",

  // مستكشف الأدلة
  "ev.title": "الأدلة",
  "ev.none": "لا شيء يشير إلى هذه الرسالة",
  "ev.refs": "{n} إشارة",
  "ev.deals": "العروض ({n})",
  "ev.decisions": "القرارات ({n})",
  "ev.briefs": "الملخصات البحثية ({n})",
  "ev.digests": "الملخصات الدورية ({n})",
  "ev.alerts": "التنبيهات ({n})",
  "ev.faqs": "الأسئلة الشائعة ({n})",
  "ev.entities": "الجهات ({n})",
  "ev.asDecision": "هذه الرسالة تنص على القرار",
  "ev.asFollowup": "هذه الرسالة متابعة بشأن القرار",
  "ev.replyTo": "رد على",
  "ev.directReplies": "الردود المباشرة ({n})",

  // كتلة المحادثة
  "conv.title": "المحادثة",
  "conv.openHint": "سلسلة الردود (حيث التُقطت) والرسائل المحيطة بهذه",
  "conv.repliesTo": "رداً على {ids}",
  "conv.directReply": "رد مباشر",
  "conv.mediaOnly": "[وسائط فقط]",
  "conv.noNeighbors": "لا رسائل مجاورة مؤرشفة حول هذه الرسالة.",
  "conv.couldNotOpen": "تعذر فتح الرسالة",

  // لوحة اسأل الذكاء
  "ai.notConfigured": "خاصية اسأل الذكاء غير مفعّلة",
  "ai.notConfiguredHint":
    "أضف AI_API_KEY (وربما AI_BASE_URL / AI_MODEL) في ملف ‎.env لتفعيل " +
    "الإجابات المبنية على أرشيفك. تعمل مع أي واجهة متوافقة مع OpenAI - " +
    "OpenAI وGroq وOpenRouter وOllama وvLLM وغيرها. أعد تشغيل التطبيق " +
    "بعد تعديل ‎.env.",
  "ai.emptyTitle": "اسأل عن أي شيء في مجموعاتك",
  "ai.emptyHint":
    "الإجابات مبنية على {n} رسالة مؤرشفة، مع استشهادات قابلة للنقر. " +
    "الأسئلة بالعربية تجيب بالعربية.",
  "ai.thinking": "أبحث في {scope} وأفكر…",
  "ai.scope": "النطاق:",
  "ai.scopeHint": "يسترجع الذكاء الرسائل ضمن هذا النطاق فقط",
  "ai.scopeGroupsHint": "إزالة عامل المجموعة - البحث في كل المجموعات المتتبعة",
  "ai.scopeAllHint": "يتبع اختيار المجموعات في الشريط الجانبي",
  "ai.scopeGroups": "{n} مجموعة",
  "ai.placeholder": "اسأل سؤالاً…  (Ctrl+Enter)",
  "ai.ask": "اسأل",
  "ai.disclosure":
    "الإجابات ترسل مقتطفات الرسائل المسترجعة إلى {host} ({model}) ضمن: " +
    "{scope}. لا يُرسل شيء إلا إذا سألت.",
  "ai.clearHistory": "مسح السجل",
  "ai.fallbackRecent": "لا نتائج للكلمات المفتاحية — الإجابة بناءً على أحدث الرسائل.",
  "ai.basedOn": "بناءً على {n} رسالة مسترجعة.",
  "ai.exporting": "جارٍ التصدير…",
  "ai.export": "تصدير ‎.md",
  "ai.exported": "تم التصدير: {name}",
  "ai.sources": "المصادر ({n})",
  "ai.badCitation": "الاستشهاد [{n}] لا يقابله رسالة مسترجعة",
  "ai.couldNotOpen": "تعذر فتح الرسالة الأصلية",
};
