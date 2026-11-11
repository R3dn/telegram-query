/** قاموس الواجهة: شاشة "system" — الإعدادات، المهام، إدارة المجموعات. */
import type { Dict } from "../types";

export const dict: Dict = {
  // عناوين الأقسام
  "system.section.general": "عام",
  "system.section.data": "البيانات",
  "system.section.appearance": "المظهر",
  "system.section.telegram": "Telegram",
  "system.section.autoSync": "المزامنة التلقائية (v0.4)",
  "system.section.normalization": "تطبيع البحث",
  "system.section.ai": "مزوّد الذكاء الاصطناعي",

  // اللغة والسمة
  "system.language": "اللغة",
  "system.theme": "السمة",
  "system.theme.dark": "داكن",
  "system.theme.light": "فاتح",

  // قسم Telegram
  "system.account": "الحساب",
  "system.loggedIn": "مسجّل الدخول",
  "system.loggedInAs": "مسجّل الدخول باسم {user}",
  "system.notLoggedIn": "غير مسجّل الدخول",
  "system.checking": "جارٍ التحقق…",
  "system.apiCredentials": "بيانات API",
  "system.configured": "مُعدّ",
  "system.missing": "غير موجودة",
  "system.change": "تغيير",
  "system.saveCredentials": "حفظ البيانات",
  "system.logoutTelegram": "تسجيل الخروج من Telegram",
  "system.loggedOut": "تم تسجيل الخروج من Telegram",
  "system.credsSaved": "تم حفظ البيانات",

  // قسم المزامنة التلقائية
  "system.autoSync": "المزامنة التلقائية",
  "system.on": "مُفعّلة",
  "system.off": "معطّلة",
  "system.interval": "الفاصل الزمني",
  "system.sched.note":
    "يُحفظ الجدول في قاعدة بياناتك المحلية ويبقى قائماً بعد إعادة التشغيل؛ وإذا كان التطبيق مغلقاً عند حلول موعد المزامنة، تعمل مزامنة تدارك واحدة عند الإقلاع التالي. ولا تتداخل المزامنة أبداً مع مهمة جارية.",
  "system.sched.next": "التالية:",
  "system.sched.last": "آخر مزامنة ناجحة:",
  "system.schedSaved": "تم حفظ إعدادات المزامنة التلقائية",

  // قسم تطبيع البحث
  "system.normLevel": "مستوى التطبيع",
  "system.normExtended": "موسّع (عربيزي · لهجة خليجية · مدّ الحروف)",
  "system.reindex": "إعادة بناء فهرس البحث",
  "system.reindexTitle":
    "إعادة كتابة فهرس البحث وفق قواعد التطبيع الحالية. تعمل كمهمة في الخلفية.",
  "system.reindexQueued": "انضمت مهمة إعادة الفهرسة إلى قائمة الانتظار — انظر {jobs}",
  "system.reindexAlready": "إعادة الفهرسة في قائمة الانتظار بالفعل",
  "system.norm.noteA":
    "يطوّي التطبيع الموسّع الأرقام العربية الهندية (٢٥ تصبح 25)، ويجمع مدّ الحروف في المحادثات (هااااي تصبح هاي)، ويطوّي أرقام العربيزي داخل الكلمات اللاتينية، ويحوّل كلمات اللهجة الخليجية الشائعة إلى صورتها الفصيحة — عند الفهرسة وعند البحث معاً، فيتطابق الطرفان دائماً. نص الرسائل الأصلي لا يُعدَّل أبداً. اضبط",
  "system.norm.noteB": "في ملف .env للسلوك القديم (v0.3)، ثم استخدم «{button}».",

  // قسم مزوّد الذكاء الاصطناعي
  "system.provider": "المزوّد",
  "system.aiNotConfigured": "غير مُعدّ",
  "system.saveProvider": "حفظ المزوّد",
  "system.aiUsage": "استخدام الذكاء الاصطناعي (هذا الجهاز)",
  "system.aiUsageTitle": "الطلبات والرموز التقديرية المسجّلة محلياً لكل ميزة",
  "system.usageBadge": "{requests} · نحو {tokens} رمز",
  "system.ai.noteA":
    "تُرسل إجابات الذكاء الاصطناعي مقتطفاتٍ من الرسائل المسترجَعة إلى نقطة نهاية المزوّد المُعدّ. تبقى المفاتيح على الخادم وتُكتب في ملف",
  "system.ai.noteB":
    "المحلي عندك، ولا تُعاد إلى المتصفح أبداً. وكل ما عدا ذلك لا يغادر هذا الجهاز.",

  // محو كل البيانات (الإعدادات ← البيانات)
  "system.eraseTitle": "محو كل البيانات",
  "system.eraseOpen": "محو…",
  "system.eraseConfirmHint":
    "يحذف هذا نهائياً أرشيفك بالكامل على هذا الجهاز: قاعدة البيانات، وجلسة Telegram، وإعداداتك. لا يمكن التراجع عنه.",
  "system.eraseTypePrompt": "اكتب {word} للتأكيد",
  "system.eraseGo": "محو كل شيء",
  "system.eraseDone": "تم محو كل البيانات — يُعاد تحميل التطبيق الآن",
  "system.eraseFailed": "فشل المحو",
  "system.eraseRowDb": "قاعدة البيانات",
  "system.eraseRowSession": "جلسة Telegram",
  "system.eraseRowConfig": "الإعدادات والنسخ الاحتياطية",

  // مركز المهام
  "system.jobs.queued": "في الانتظار",
  "system.jobs.usingSession": "المهمة الحالية تستخدم جلسة Telegram.",
  "system.jobs.noneRunning": "لا توجد مهمة قيد التنفيذ.",
  "system.jobs.runsAfter": "تعمل بعد انتهاء المهمة الحالية.",
  "system.jobs.stoppingSaved": "سيتم الإيقاف عند نقطة التحقق التالية — التقدّم محفوظ",
  "system.jobs.cancelledQueued": "أُلغيت المهام المنتظرة: {jobs}",
  "system.jobs.retrySync": "إعادة المحاولة: المزامنة في قائمة الانتظار",
  "system.jobs.retryDialogs": "إعادة المحاولة: جلب قائمة المجموعات في قائمة الانتظار",
  "system.jobs.retryTrack": "افتح «{manage}» لإعادة محاولة التتبّع",
  "system.jobs.stopCurrent": "إيقاف المهمة الحالية",
  "system.jobs.cancelQueued": "إلغاء {n} في الانتظار",
  "system.jobs.retryLast": "إعادة المهمة الأخيرة",
  "system.refresh": "تحديث",
  "system.jobs.liveLog": "السجل المباشر",
  "system.jobs.noOutput": "(لا مخرجات بعد)",

  // إدارة المجموعات
  "system.mm.loadingGroups": "جارٍ جلب مجموعاتك من Telegram…",
  "system.mm.waitingJob": "بانتظار {job}… أوقفها إن كنت تحتاج القائمة الآن",
  "system.mm.loadFailed": "تعذّر جلب قائمة المجموعات من Telegram",
  "system.mm.tickFirst": "حدّد أولاً المجموعات التي تريد تتبّعها",
  "system.mm.trackedQueued": "بدأ تتبّع {groups} — بانتظار {jobs}",
  "system.mm.trackedBackfill": "بدأ تتبّع {groups} — يجري استكمال السجل الكامل",
  "system.mm.untrackedDeleted": "أُلغي التتبّع — حُذفت الرسائل نهائياً",
  "system.mm.untrackedKept": "أُلغي التتبّع — بقيت الرسائل على القرص (أعد التتبّع لاستعادتها)",
  "system.mm.allTracked": "كل مجموعاتك في Telegram متابَعة بالفعل.",
  "system.mm.trackSelected": "تتبّع المحدد",
  "system.mm.reloadList": "إعادة تحميل قائمة Telegram",
  "system.mm.trackedSection": "المجموعات المتابَعة",
  "system.mm.othersSection": "مجموعات Telegram غير المتابَعة بعد",
  "system.mm.noneTrackedHint": "لا توجد مجموعات متابَعة بعد — اختر بعضها أدناه.",
  "system.mm.untrack": "إلغاء التتبّع",
  "system.mm.untrackArmed": "ستبقى الرسائل — متأكد؟",
  "system.mm.deleteArmed": "حذف {n} رسالة — متأكد؟",
  "system.mm.untrackTitle":
    "إيقاف أرشفة هذه المجموعة. تبقى الرسائل على القرص وتعود إذا تتبّعتها مجدداً.",
  "system.mm.deleteTitle": "حذف رسائل هذه المجموعة من الأرشيف نهائياً.",
  "system.mm.fetching": "جارٍ جلب قائمة مجموعاتك من Telegram…",
  "system.mm.stoppingList": "جارٍ الإيقاف — تُحمَّل القائمة بعده",
  "system.lastMessage": "آخرها {date}",
  "system.starting": "(جارٍ البدء…)",
  "system.alreadyTracking": "هذه المجموعات متابَعة بالفعل",
  "system.trackFailed": "تعذّر بدء التتبّع",

  // أسماء العدد حسب تصنيف الجمع العربي
  "system.pl.group.one": "مجموعة واحدة",
  "system.pl.group.two": "مجموعتان",
  "system.pl.group.few": "{n} مجموعات",
  "system.pl.group.many": "{n} مجموعة",
  "system.pl.job.one": "مهمة واحدة",
  "system.pl.job.two": "مهمتان",
  "system.pl.job.few": "{n} مهام",
  "system.pl.job.many": "{n} مهمة",
  "system.pl.request.one": "طلب واحد",
  "system.pl.request.two": "طلبان",
  "system.pl.request.few": "{n} طلبات",
  "system.pl.request.many": "{n} طلباً",
};
