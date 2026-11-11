/** قاموس الواجهة: الهوية، التنقل، حالة المزامنة، الشريط السفلي،
 *  اللوحة اليمنى، والإجراءات المشتركة بين الشاشات. */
import type { Dict } from "../types";

export const dict: Dict = {
  "app.name": "تيليجرام كويري",

  // مجموعات التنقل والعناصر
  "nav.discover": "الاستكشاف",
  "nav.entities": "الجهات",
  "nav.browse": "التصفح والبحث",
  "nav.askAi": "اسأل الذكاء",
  "nav.bookmarks": "المحفوظات",
  "nav.jobs": "المهام",
  "nav.deals": "العروض",
  "nav.decisions": "القرارات",
  "nav.research": "الأبحاث",
  "nav.faqs": "الأسئلة الشائعة",
  "nav.watchlists": "قوائم المراقبة",
  "nav.alerts": "التنبيهات",
  "nav.digests": "الملخصات",
  "nav.group.discover": "استكشاف",
  "nav.group.knowledge": "المعرفة",
  "nav.group.monitor": "المراقبة",
  "nav.groups": "المجموعات",

  // قسم المجموعات
  "groups.filterPlaceholder": "تصفية المجموعات…",
  "groups.all": "كل المجموعات",
  "groups.messagesCount": "{n} رسالة",
  "groups.msgs": "{n} رسالة",
  "groups.noMatch": "لا توجد مجموعات مطابقة.",
  "groups.noneTracked": "لم تُضف أي مجموعات بعد.",
  "groups.manage": "إدارة المجموعات",
  "groups.channel": "قناة",
  "groups.group": "مجموعة",

  // عمليات البحث المحفوظة
  "saved.title": "عمليات بحث محفوظة",
  "saved.rename": "إعادة تسمية",
  "saved.duplicate": "نسخ",
  "saved.delete": "حذف",
  "saved.clickAgain": "انقر مرة أخرى للحذف",
  "saved.filtersOnly": "عوامل تصفية فقط",
  "saved.browseWith": "تصفح بهذه العوامل",

  // بطاقة المزامنة
  "sync.running": "جارٍ تنفيذ {job}…",
  "sync.done": "اكتمل {job}",
  "sync.failed": "فشل {job}",
  "sync.idle": "خامل",
  "sync.queued": "{n} في الانتظار",
  "sync.autoNext": "مزامنة تلقائية {interval} · التالية {time}",
  "sync.configureHint": "التهيئة من الإعدادات",
  "sync.lastOk": "آخر نجاح {when}",
  "sync.backfills": "{n} من الاستكمالات يمكن استئنافها",
  "sync.now": "مزامنة الآن",
  "sync.details": "التفاصيل",
  "sync.started": "بدأت المزامنة",
  "sync.alreadyQueued": "المزامنة في قائمة الانتظار بالفعل",

  // تذييل الشريط
  "shell.setupWizard": "معالج الإعداد",
  "shell.settings": "الإعدادات",

  // اللوحة اليمنى
  "panel.askAi": "اسأل الذكاء",
  "panel.details": "التفاصيل",
  "panel.detailsHint": "اختر رسالة لعرض التفاصيل",
  "panel.dragResize": "اسحب لتغيير الحجم",
  "panel.show": "إظهار اللوحة",
  "panel.hide": "إخفاء اللوحة",

  // إجراءات مشتركة
  "action.clear": "مسح",
  "action.close": "إغلاق",
  "action.cancel": "إلغاء",
  "action.save": "حفظ",
  "action.delete": "حذف",
  "action.rename": "إعادة تسمية",
  "action.confirm": "تأكيد",
  "action.copy": "نسخ النص",
  "action.copied": "تم النسخ",
  "action.openTelegram": "فتح في تيليجرام",
  "action.viewConversation": "عرض في المحادثة",
  "action.view": "عرض",
  "state.loading": "جارٍ التحميل…",

  // تسميات قصيرة للشريط السفلي (لا تطابق أسماء أزرار الشريط الجانبي)
  "nav.browseShort": "تصفح",

  // أسماء مهام الخلفية
  "job.sync": "المزامنة",
  "job.track": "استكمال سجل المجموعة",
  "job.dialogs": "جلب قائمة المجموعات",
  "job.auth": "تسجيل الدخول",
  "job.reindex": "إعادة الفهرسة",
  "job.discover": "استكمال سجل الاستكشاف",
  "job.extract": "استخراج العروض",
  "job.decisions": "استخراج القرارات",
  "job.brief": "ملخص بحثي",
  "job.unknown": "مهمة",
  "job.finished": "اكتملت",
  "job.failed": "فشلت",

  // فواصل المجدول الزمنية
  "interval.everyDay": "يومياً",
  "interval.everyDays": "كل {n} أيام",
  "interval.everyHours": "كل {n} ساعة",
  "interval.everyMin": "كل {n} دقيقة",
};
