/** قاموس الواجهة: شاشة "faqs" — الأسئلة المتكررة والإجابات المقترحة. */
import type { Dict } from "../types";

export const dict: Dict = {
  // الشريط العلوي وتبويبات الحالة
  "faqs.discover": "اكتشاف الأسئلة",
  "faqs.discoverHint": "فحص آخر 90 يوماً للأسئلة المتكررة",
  "faqs.aiRequired": "هيّئ مزوّد ذكاء اصطناعي أولاً",
  "faqs.tabAll": "الكل",
  "faqs.st.candidate": "مرشَّح",
  "faqs.st.approved": "مُعتمد",
  "faqs.st.needs_review": "بحاجة إلى مراجعة",
  "faqs.st.rejected": "مرفوض",
  "faqs.st.outdated": "متقادم",

  // نطاق الاكتشاف
  "faqs.scopeLabel": "نطاق الاكتشاف (المجموعات):",

  // حالات الفراغ
  "faqs.emptyAll": "لا أسئلة شائعة بعد",
  "faqs.emptyCandidate": "لا أسئلة مرشَّحة",
  "faqs.emptyApproved": "لا أسئلة معتمدة",
  "faqs.emptyReview": "لا أسئلة بحاجة إلى مراجعة",
  "faqs.emptyRejected": "لا أسئلة مرفوضة",
  "faqs.emptyHintAi":
    "شغّل «اكتشاف الأسئلة» لتجميع الأسئلة التي تطرحها مجموعاتك " +
    "باستمرار. الإجابات المقترحة تستشهد برسائل حقيقية؛ ولا يتحول أي " +
    "شيء إلى معرفة موثوقة قبل أن تعتمده.",
  "faqs.emptyHintAiOff":
    "هيّئ مزوّد ذكاء اصطناعي (من الإعدادات) لصياغة الإجابات. تجميع " +
    "الأسئلة نفسه حتمي.",

  // البطاقات
  "faqs.freq": "×{n}",
  "faqs.lastSeen": "آخر ظهور: {date}",
  "faqs.approve": "اعتماد",
  "faqs.approvedToast": "تم الاعتماد",
  "faqs.stillCorrect": "ما زالت صحيحة",
  "faqs.stillCorrectHint": "إعادة الاعتماد بعد مراجعة الدليل الجديد",
  "faqs.reapproved": "أُعيد الاعتماد",
  "faqs.noAnswerYet": "لا إجابة مصاغة بعد — شغّل الاكتشاف مجدداً",

  // نافذة التفاصيل
  "faqs.noDraftedAnswer": "لا إجابة مصاغة بعد.",
  "faqs.askedSources": "سُئل {n} مرة — مصادر السؤال",
  "faqs.deleted": "[محذوف]",
  "faqs.saveAnswer": "حفظ الإجابة",
  "faqs.answerSaved": "تم حفظ الإجابة",
  "faqs.editAnswer": "تعديل الإجابة",
  "faqs.markOutdated": "تحديد كمتقادم",
  "faqs.markedOutdated": "حُدِّد كمتقادم",
  "faqs.deletedToast": "حُذف السؤال",
  "faqs.queued": "قُيّد اكتشاف الأسئلة في قائمة الانتظار — تابعه في المهام",
  "faqs.discoveryRunning": "الاكتشاف يعمل بالفعل",
};
