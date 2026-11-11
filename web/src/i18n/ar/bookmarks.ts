/** قاموس الواجهة: شاشة "المحفوظات". */
import type { Dict } from "../types";

export const dict: Dict = {
  // شريط الأدوات الثابت
  "bookmarks.title": "المحفوظات",
  "bookmarks.searchPlaceholder": "ابحث في الملاحظات والرسائل…",
  "bookmarks.exportMd": "تصدير ‎.md",
  "bookmarks.exportJson": "تصدير ‎.json",
  "bookmarks.exportDone": "تم التصدير: {name}",

  // إجراءات الصف
  "bookmarks.jump": "انتقال",
  "bookmarks.telegram": "تيليجرام",
  "bookmarks.copyLink": "نسخ الرابط",
  "bookmarks.linkCopied": "تم نسخ الرابط",
  "bookmarks.copyFailed": "فشل النسخ",

  // حالات الفراغ
  "bookmarks.emptyTitle": "لا محفوظات بعد",
  "bookmarks.emptyHint":
    "ميّز الرسائل بنجمة في التدفق (أو في لوحة التفاصيل) لتبقى هنا. " +
    "الملاحظات تبقى على هذا الجهاز ولا تُرسل إلى الذكاء الاصطناعي أبداً.",
  "bookmarks.noMatchTitle": "لا محفوظات مطابقة",
  "bookmarks.noMatchHint": "لا شيء يطابق هذا البحث. جرّب كلمة مختلفة.",
};
