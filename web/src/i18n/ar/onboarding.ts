/** قاموس الواجهة: شاشة "onboarding" — معالج الإعداد ونماذجه. */
import type { Dict } from "../types";

export const dict: Dict = {
  // هيكل المعالج
  "onboarding.welcome": "مرحباً بك في {app}",
  "onboarding.closeHint": "إغلاق — يمكنك إعادة فتح المعالج من الشريط الجانبي",
  "onboarding.step.credentials": "بيانات Telegram API",
  "onboarding.step.login": "تسجيل الدخول إلى Telegram",
  "onboarding.step.groups": "اختيار المجموعات المتابَعة",
  "onboarding.step.ai": "مزوّد الذكاء الاصطناعي (اختياري)",
  "onboarding.step.sync": "أول مزامنة",
  "onboarding.allSet": "اكتمل الإعداد — يمكنك إغلاق هذا المعالج.",
  "onboarding.startUsing": "ابدأ باستخدام {app}",
  "onboarding.editCreds": "تغيير بيانات API…",
  "onboarding.setupComplete": "اكتمل الإعداد — أرشيفك في طور البناء",
  "onboarding.continue": "متابعة",
  "onboarding.skip": "التخطي الآن",
  "onboarding.checking": "جارٍ التحقق…",

  // خطوة بيانات الاعتماد
  "onboarding.creds.title": "اربط حسابك في Telegram",
  "onboarding.creds.intro":
    "يشترط Telegram على كل تطبيق خارجي استخدام بيانات API خاصة به — إنشاؤها لا يستغرق سوى دقيقة تقريباً:",
  "onboarding.creds.step1.open": "افتح",
  "onboarding.creds.step1.tools": "API development tools",
  "onboarding.creds.step2": "أنشئ تطبيقاً (بأي اسم؛ ويمكن ترك بقية الخيارات كما هي)",
  "onboarding.creds.step3.copy": "انسخ",
  "onboarding.creds.step3.and": "و",
  "onboarding.creds.step3.paste": "ثم الصقهما أدناه",
  "onboarding.creds.envNote.a": "تُحفظ القيم في ملف",
  "onboarding.creds.envNote.b": "المحلي عندك. تفضّل تعديل الملفات مباشرة؟ كل شيء موثّق في",
  "onboarding.recheckEnv": "عدّلت ملف .env يدوياً — تحقق مجدداً",

  // خطوة تسجيل الدخول
  "onboarding.login.phone": "رقم الهاتف (بالصيغة الدولية)",
  "onboarding.login.send": "إرسال رمز الدخول",
  "onboarding.login.sending": "جارٍ إرسال الرمز…",
  "onboarding.login.codeSent":
    "أرسل Telegram رمز دخول إلى تطبيقك أو عبر رسالة نصية. أدخله أدناه.",
  "onboarding.login.code": "رمز الدخول",
  "onboarding.login.verify": "تحقّق",
  "onboarding.login.verifying": "جارٍ التحقق…",
  "onboarding.login.resend": "إعادة الإرسال",
  "onboarding.login.2faIntro":
    "حسابك مفعّل عليه التحقق بخطوتين. أدخل كلمة مرور السحابة.",
  "onboarding.login.2faPassword": "كلمة مرور التحقق بخطوتين",
  "onboarding.login.loggedInAs": "تم تسجيل الدخول باسم {user}",

  // خطوة المجموعات
  "onboarding.groups.intro":
    "تُنسخ المجموعات المتابَعة إلى أرشيفك المحلي — ويُنزَّل سجلها الكامل لتتمكن من البحث فيها وتصفحها. يمكنك تغيير اختيارك في أي وقت من «{manage}».",
  "onboarding.groups.load": "جلب مجموعاتي",
  "onboarding.groups.listing": "جارٍ سرد مجموعاتك…",
  "onboarding.groups.reload": "إعادة تحميل القائمة",
  "onboarding.groups.track": "تابِع",
  "onboarding.groups.pickAtLeastOne": "حدّد مجموعة واحدة على الأقل",
  "onboarding.groups.loadTimeout": "انتهت مهلة تحميل قائمة المجموعات",

  // خطوة الذكاء الاصطناعي
  "onboarding.ai.optional": "اختياري",
  "onboarding.ai.intro":
    "يجيب «اسأل الذكاء» عن أسئلتك المتعلقة بأرشيفك عبر أي نقطة نهاية متوافقة مع OpenAI (مثل OpenAI وGroq وOpenRouter وOllama وLM Studio وvLLM…). يمكنك اختبار الاتصال قبل الحفظ.",
  "onboarding.ai.recheck": "إعادة الفحص",
  "onboarding.ai.privacyNote":
    "لا تُرسَل إلى نقطة النهاية إلا مقتطفات الرسائل المسترجَعة حين تطرح سؤالاً — أما بقية أرشيفك فلا تغادر هذا الجهاز أبداً.",

  // خطوة أول مزامنة
  "onboarding.sync.intro":
    "يجري الآن تنزيل سجل مجموعاتك المتابَعة. قد تستغرق المجموعات الكبيرة وقتاً — يمكنك مواصلة استخدام التطبيق وإيقاف المزامنة واستئنافها متى شئت دون فقدان أي تقدّم.",
  "onboarding.sync.start": "بدء أول مزامنة",
  "onboarding.sync.backfilling": "جارٍ استكمال سجل مجموعتك…",
  "onboarding.sync.syncing": "جارٍ المزامنة…",
  "onboarding.sync.queuedBehind": "في قائمة الانتظار خلف {jobs}…",
  "onboarding.sync.queuedStarting": "المزامنة في قائمة الانتظار — جارٍ البدء…",
  "onboarding.sync.starting": "(جارٍ البدء…)",
  "onboarding.sync.stop": "إيقاف (التقدّم محفوظ)",
  "onboarding.sync.finish": "إنهاء الإعداد",

  // نماذج الإعداد المشتركة (المعالج + الإعدادات)
  "onboarding.form.apiId": "معرّف API",
  "onboarding.form.apiHash": "هاش API",
  "onboarding.form.show": "إظهار",
  "onboarding.form.hide": "إخفاء",
  "onboarding.form.saving": "جارٍ الحفظ…",
  "onboarding.form.saveContinue": "حفظ ومتابعة",
  "onboarding.form.preset": "القالب الجاهز للمزوّد",
  "onboarding.form.presetOllama": "Ollama (محلي)",
  "onboarding.form.presetCustom": "مخصّص…",
  "onboarding.form.endpoint": "نقطة النهاية (العنوان الأساسي)",
  "onboarding.form.apiKey": "مفتاح API",
  "onboarding.form.keyAny": "أي قيمة غير فارغة (مثلاً ollama)",
  "onboarding.form.model": "الموديل",
  "onboarding.form.test": "اختبار الاتصال",
  "onboarding.form.testing": "جارٍ الاختبار…",
  "onboarding.form.testOk": "ردّ {model} — الاتصال يعمل",
  "onboarding.form.keyNote.a": "يُحفظ المفتاح في ملف",
  "onboarding.form.keyNote.b": "المحلي عندك، ولا يُعرض مجدداً ولا يُعاد إلى المتصفح.",
};
