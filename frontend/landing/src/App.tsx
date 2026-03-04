import React, { useState, useContext } from 'react';
import { motion, useScroll, useTransform, AnimatePresence } from 'motion/react';
import {
  MessageCircle,
  Globe2,
  PackageSearch,
  Handshake,
  FileText,
  ArrowRight,
  ArrowLeft,
  Bot,
  Sparkles,
  Zap,
  CheckCircle2,
  Languages,
  X,
  Menu
} from 'lucide-react';

const translations = {
  en: {
    nav: { features: "Features", integrations: "Integrations", howItWorks: "How it works", login: "Войти" },
    hero: {
      badge: "AI-assistant for B2B sales",
      title1: "A new era of sales in ",
      title2: " with AI",
      desc: "Automate customer communication, check stock, and create quotes 24/7. Your perfect salesperson who never sleeps.",
      startFree: "Войти",
      watchDemo: "Watch demo",
      noCard: "No credit card required",
      setup: "5-minute setup",
      chat1: "Hi! Do you have the Ergonomic Office Chair V2 in stock?",
      chat2: "Hello! Yes, we currently have 45 units of the Ergonomic Office Chair V2 in our Dubai warehouse. The price is $299 each.",
      chat3: "Great! Can you send me a quote for 10 units?",
      chat4: "Absolutely! I've generated a Sale Order for 10 units.",
      synced: "Zoho Inventory Synced",
      langTitle: "Language",
      langDesc: "English & Arabic",
      quoteName: "Quote_SO-2049.pdf",
      quoteDesc: "1.2 MB • Generated via Zoho CRM"
    },
    features: {
      title: "Everything you need for sales",
      desc: "Treejar AI combines the power of AI with your favorite business tools.",
      f1Title: "Fluent in 2+ languages",
      f1Desc: "The bot perfectly understands context and communicates with clients in English and Arabic, adapting to their style.",
      f2Title: "Live inventory sync",
      f2Desc: "Direct integration with Zoho Inventory. The bot always knows the exact stock quantity.",
      f3Title: "Human-free deal creation",
      f3Desc: "Automatic lead and deal creation in Zoho CRM after qualification in WhatsApp.",
      f4Title: "Instant PDF quotes",
      f4Desc: "Generate beautiful Sale Orders and send them directly to the client's chat in seconds."
    },
    integrations: {
      title: "Seamless integration",
      desc: "Works where your clients are, and syncs with what you use."
    },
    footer: {
      rights: "© 2026 Treejar Trading LLC. All rights reserved.",
      privacy: "Privacy Policy",
      terms: "Terms of Service"
    },
    legal: {
      privacy: {
        title: "Privacy Policy",
        lastUpdated: "Last Updated: March 2026",
        sections: [
          {
            heading: "1. Introduction",
            text: "Welcome to Treejar AI, operated by Treejar Trading LLC. We are committed to protecting your privacy and ensuring compliance with the UAE Federal Decree-Law No. 45 of 2021 regarding the Protection of Personal Data (PDPL)."
          },
          {
            heading: "2. Data Collection",
            text: "We collect and process business contact information, WhatsApp phone numbers, chat histories, and transactional data necessary to provide our AI sales assistant services and integrate with your Zoho CRM and Inventory systems."
          },
          {
            heading: "3. Data Processing & Sharing",
            text: "Your data is processed securely using Meta's official WhatsApp Business API and Zoho's infrastructure. We do not sell, rent, or trade your personal or business data to third parties for marketing purposes."
          },
          {
            heading: "4. Data Security",
            text: "We implement industry-standard encryption and security measures to protect your data against unauthorized access, alteration, or destruction, in accordance with UAE cybersecurity regulations."
          },
          {
            heading: "5. Your Rights",
            text: "Under the UAE PDPL, you have the right to request access to, correction of, or deletion of your personal data. To exercise these rights, please contact our Data Protection Officer."
          },
          {
            heading: "6. Contact Us",
            text: "For any privacy-related inquiries, please contact us at legal@treejartrading.ae or visit our office in Dubai, United Arab Emirates."
          }
        ]
      },
      terms: {
        title: "Terms of Service",
        lastUpdated: "Last Updated: March 2026",
        sections: [
          {
            heading: "1. Acceptance of Terms",
            text: "By accessing and using Treejar AI, you agree to be bound by these Terms of Service. If you do not agree with any part of these terms, you must not use our services."
          },
          {
            heading: "2. Description of Service",
            text: "Treejar AI provides an automated B2B sales assistant integrated with WhatsApp and Zoho ecosystem. The service is intended for legitimate business use only."
          },
          {
            heading: "3. User Obligations",
            text: "You agree to use the service in compliance with all applicable laws of the United Arab Emirates, including the UAE Cybercrime Law (Federal Decree-Law No. 34 of 2021). You shall not use the service to send spam, unsolicited promotions, or illegal content."
          },
          {
            heading: "4. Limitation of Liability",
            text: "To the maximum extent permitted by UAE law, Treejar Trading LLC shall not be liable for any indirect, incidental, special, consequential, or punitive damages, or any loss of profits or revenues resulting from your use of the service."
          },
          {
            heading: "5. Governing Law & Jurisdiction",
            text: "These Terms shall be governed by and construed in accordance with the laws of the United Arab Emirates. Any disputes arising out of or in connection with these terms shall be subject to the exclusive jurisdiction of the Courts of Dubai."
          }
        ]
      }
    }
  },
  ar: {
    nav: { features: "الميزات", integrations: "التكامل", howItWorks: "كيف يعمل", login: "تسجيل الدخول" },
    hero: {
      badge: "مساعد ذكي لمبيعات B2B",
      title1: "عصر جديد للمبيعات في ",
      title2: " مع الذكاء الاصطناعي",
      desc: "أتمتة التواصل مع العملاء، التحقق من المخزون، وإنشاء عروض الأسعار على مدار الساعة. مندوب مبيعاتك المثالي الذي لا ينام.",
      startFree: "ابدأ مجانًا",
      watchDemo: "مشاهدة العرض التوضيحي",
      noCard: "لا يتطلب بطاقة ائتمان",
      setup: "إعداد في 5 دقائق",
      chat1: "مرحباً! هل لديكم كرسي المكتب المريح V2 في المخزون؟",
      chat2: "أهلاً! نعم، لدينا حاليًا 45 وحدة من كرسي المكتب المريح V2 في مستودعنا بدبي. السعر 299 دولارًا لكل وحدة.",
      chat3: "رائع! هل يمكنك إرسال عرض أسعار لـ 10 وحدات؟",
      chat4: "بالتأكيد! لقد قمت بإنشاء طلب مبيعات لـ 10 وحدات.",
      synced: "متزامن مع Zoho Inventory",
      langTitle: "اللغة",
      langDesc: "الإنجليزية والعربية",
      quoteName: "Quote_SO-2049.pdf",
      quoteDesc: "1.2 MB • تم الإنشاء عبر Zoho CRM"
    },
    features: {
      title: "كل ما تحتاجه للمبيعات",
      desc: "يجمع Treejar AI بين قوة الذكاء الاصطناعي وأدوات العمل المفضلة لديك.",
      f1Title: "طلاقة في لغتين وأكثر",
      f1Desc: "يفهم البوت السياق تمامًا ويتواصل مع العملاء باللغتين الإنجليزية والعربية، ويتكيف مع أسلوبهم.",
      f2Title: "مزامنة المخزون المباشرة",
      f2Desc: "تكامل مباشر مع Zoho Inventory. يعرف البوت دائمًا كمية المخزون الدقيقة.",
      f3Title: "إنشاء صفقات بدون تدخل بشري",
      f3Desc: "إنشاء تلقائي للعملاء المحتملين والصفقات في Zoho CRM بعد التأهيل في WhatsApp.",
      f4Title: "عروض أسعار PDF فورية",
      f4Desc: "إنشاء طلبات مبيعات جميلة وإرسالها مباشرة إلى دردشة العميل في ثوانٍ."
    },
    integrations: {
      title: "تكامل سلس",
      desc: "يعمل حيث يتواجد عملاؤك، ويتزامن مع ما تستخدمه."
    },
    footer: {
      rights: "© 2026 Treejar Trading LLC. جميع الحقوق محفوظة.",
      privacy: "سياسة الخصوصية",
      terms: "شروط الخدمة"
    },
    legal: {
      privacy: {
        title: "سياسة الخصوصية",
        lastUpdated: "آخر تحديث: مارس 2026",
        sections: [
          {
            heading: "1. مقدمة",
            text: "مرحباً بكم في Treejar AI، المشغلة بواسطة Treejar Trading LLC. نحن ملتزمون بحماية خصوصيتك وضمان الامتثال للمرسوم بقانون اتحادي رقم 45 لسنة 2021 بشأن حماية البيانات الشخصية (PDPL) في دولة الإمارات العربية المتحدة."
          },
          {
            heading: "2. جمع البيانات",
            text: "نقوم بجمع ومعالجة معلومات الاتصال التجارية، وأرقام هواتف WhatsApp، وسجلات الدردشة، وبيانات المعاملات اللازمة لتقديم خدمات مساعد المبيعات الذكي الخاص بنا والتكامل مع أنظمة Zoho CRM و Inventory الخاصة بك."
          },
          {
            heading: "3. معالجة البيانات ومشاركتها",
            text: "تتم معالجة بياناتك بشكل آمن باستخدام واجهة برمجة تطبيقات WhatsApp Business الرسمية من Meta وبنية Zoho التحتية. نحن لا نبيع أو نؤجر أو نتاجر ببياناتك الشخصية أو التجارية لأطراف ثالثة لأغراض التسويق."
          },
          {
            heading: "4. أمن البيانات",
            text: "نحن نطبق معايير التشفير والأمان المتوافقة مع معايير الصناعة لحماية بياناتك من الوصول غير المصرح به أو التغيير أو التدمير، وفقاً للوائح الأمن السيبراني في دولة الإمارات العربية المتحدة."
          },
          {
            heading: "5. حقوقك",
            text: "بموجب قانون حماية البيانات الشخصية الإماراتي، يحق لك طلب الوصول إلى بياناتك الشخصية أو تصحيحها أو حذفها. لممارسة هذه الحقوق، يرجى الاتصال بمسؤول حماية البيانات لدينا."
          },
          {
            heading: "6. اتصل بنا",
            text: "لأي استفسارات تتعلق بالخصوصية، يرجى الاتصال بنا على legal@treejartrading.ae أو زيارة مكتبنا في دبي، الإمارات العربية المتحدة."
          }
        ]
      },
      terms: {
        title: "شروط الخدمة",
        lastUpdated: "آخر تحديث: مارس 2026",
        sections: [
          {
            heading: "1. قبول الشروط",
            text: "من خلال الوصول إلى Treejar AI واستخدامه، فإنك توافق على الالتزام بشروط الخدمة هذه. إذا كنت لا توافق على أي جزء من هذه الشروط، يجب عليك عدم استخدام خدماتنا."
          },
          {
            heading: "2. وصف الخدمة",
            text: "يوفر Treejar AI مساعد مبيعات B2B آلي متكامل مع WhatsApp ونظام Zoho البيئي. الخدمة مخصصة للاستخدام التجاري المشروع فقط."
          },
          {
            heading: "3. التزامات المستخدم",
            text: "أنت توافق على استخدام الخدمة وفقاً لجميع القوانين المعمول بها في دولة الإمارات العربية المتحدة، بما في ذلك قانون مكافحة الشائعات والجرائم الإلكترونية (المرسوم بقانون اتحادي رقم 34 لسنة 2021). يجب ألا تستخدم الخدمة لإرسال بريد عشوائي أو عروض ترويجية غير مرغوب فيها أو محتوى غير قانوني."
          },
          {
            heading: "4. حدود المسؤولية",
            text: "إلى أقصى حد يسمح به قانون دولة الإمارات العربية المتحدة، لن تكون Treejar Trading LLC مسؤولة عن أي أضرار غير مباشرة أو عرضية أو خاصة أو تبعية أو تأديبية، أو أي خسارة في الأرباح أو الإيرادات الناتجة عن استخدامك للخدمة."
          },
          {
            heading: "5. القانون الحاكم والاختصاص القضائي",
            text: "تخضع هذه الشروط وتفسر وفقاً لقوانين دولة الإمارات العربية المتحدة. تخضع أي نزاعات تنشأ عن أو فيما يتعلق بهذه الشروط للاختصاص القضائي الحصري لمحاكم دبي."
          }
        ]
      }
    }
  }
};

type Language = 'en' | 'ar';
const LanguageContext = React.createContext<{ lang: Language, setLang: (l: Language) => void }>({ lang: 'en', setLang: () => { } });

const useTranslation = () => {
  const { lang } = useContext(LanguageContext);
  return { t: translations[lang], lang };
};

const handleLogin = () => {
  console.log('Login clicked');
};

const Header = () => {
  const { t, lang } = useTranslation();
  const { setLang } = useContext(LanguageContext);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <motion.header
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200/50"
    >
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 h-16 sm:h-20 flex items-center justify-between">
        <div className="flex items-center gap-2 cursor-pointer" dir="ltr">
          <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center p-1">
            <img src="/logo.svg" alt="Treejar Logo" className="w-full h-full object-contain" />
          </div>
          <span className="font-bold text-xl sm:text-2xl tracking-tight">Treejar<span className="text-brand-orange">.AI</span></span>
        </div>

        <nav className="hidden md:flex items-center gap-8 font-medium text-slate-600">
          <a href="#features" className="hover:text-brand-black transition-colors">{t.nav.features}</a>
          <a href="#integrations" className="hover:text-brand-black transition-colors">{t.nav.integrations}</a>
          <a href="#how-it-works" className="hover:text-brand-black transition-colors">{t.nav.howItWorks}</a>
        </nav>

        <div className="flex items-center gap-2 sm:gap-4">
          <button
            onClick={() => setLang(lang === 'en' ? 'ar' : 'en')}
            className="flex items-center gap-1 sm:gap-2 text-slate-600 hover:text-brand-black font-medium transition-colors p-2"
          >
            <Languages className="w-4 h-4 sm:w-5 sm:h-5" />
            <span className="uppercase text-xs sm:text-sm">{lang === 'en' ? 'AR' : 'EN'}</span>
          </button>
          <button
            onClick={handleLogin}
            className="hidden sm:flex bg-brand-black text-white px-5 py-2 sm:px-6 sm:py-2.5 rounded-full font-medium hover:bg-slate-800 transition-all active:scale-95 items-center gap-2 text-sm sm:text-base"
          >
            {t.nav.login}
            {lang === 'ar' ? <ArrowLeft className="w-4 h-4" /> : <ArrowRight className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden p-2 text-slate-600 hover:text-brand-black"
          >
            {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden border-t border-slate-100 bg-white overflow-hidden"
          >
            <div className="px-4 py-6 flex flex-col gap-4">
              <a href="#features" onClick={() => setIsMobileMenuOpen(false)} className="text-lg font-medium text-slate-600 hover:text-brand-black">{t.nav.features}</a>
              <a href="#integrations" onClick={() => setIsMobileMenuOpen(false)} className="text-lg font-medium text-slate-600 hover:text-brand-black">{t.nav.integrations}</a>
              <a href="#how-it-works" onClick={() => setIsMobileMenuOpen(false)} className="text-lg font-medium text-slate-600 hover:text-brand-black">{t.nav.howItWorks}</a>
              <button
                onClick={() => { handleLogin(); setIsMobileMenuOpen(false); }}
                className="mt-4 bg-brand-black text-white px-6 py-3 rounded-full font-medium hover:bg-slate-800 transition-all flex items-center justify-center gap-2"
              >
                {t.nav.login}
                {lang === 'ar' ? <ArrowLeft className="w-4 h-4" /> : <ArrowRight className="w-4 h-4" />}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
};

const Hero = () => {
  const { t, lang } = useTranslation();
  const { scrollY } = useScroll();

  // Parallax effects: positive Y values make elements move slower than the scroll speed (creating depth)
  const yBg = useTransform(scrollY, [0, 1000], [0, 500]); // Deep background moves slowest
  const yChat = useTransform(scrollY, [0, 1000], [0, 250]); // Midground moves medium speed
  const yText = useTransform(scrollY, [0, 1000], [0, 50]); // Foreground text moves almost normally

  const isRtl = lang === 'ar';

  return (
    <section className="relative pt-28 pb-16 md:pt-32 md:pb-20 lg:pt-48 lg:pb-32 overflow-hidden">
      {/* Background gradients */}
      <motion.div
        style={{ y: yBg }}
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] opacity-30 pointer-events-none"
      >
        <div className="absolute inset-0 bg-gradient-to-b from-brand-soft to-transparent rounded-full blur-3xl" />
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-orange/10 rounded-full blur-3xl" />
      </motion.div>

      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 relative z-10">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          <motion.div
            style={{ y: yText }}
            className="max-w-2xl"
          >
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-orange/10 text-brand-orange font-medium text-sm mb-6 sm:mb-8 border border-brand-orange/20"
            >
              <Sparkles className="w-4 h-4" />
              <span>{t.hero.badge}</span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1, ease: "easeOut" }}
              className="text-4xl sm:text-5xl lg:text-7xl font-extrabold leading-[1.1] tracking-tight mb-4 sm:mb-6"
            >
              {t.hero.title1}<span className="text-transparent bg-clip-text bg-gradient-to-r from-[#25D366] to-[#128C7E]" dir="ltr">WhatsApp</span>{t.hero.title2}
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
              className="text-base sm:text-lg lg:text-xl text-slate-600 mb-8 sm:mb-10 leading-relaxed font-light"
            >
              {t.hero.desc}
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3, ease: "easeOut" }}
              className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4"
            >
              <button
                onClick={handleLogin}
                className="w-full sm:w-auto bg-brand-orange text-white px-6 py-3 sm:px-8 sm:py-4 rounded-full font-semibold text-base sm:text-lg hover:bg-[#e56612] transition-all hover:shadow-xl hover:shadow-brand-orange/25 active:scale-95 flex items-center justify-center gap-2"
              >
                {t.hero.startFree}
                {isRtl ? <ArrowLeft className="w-5 h-5" /> : <ArrowRight className="w-5 h-5" />}
              </button>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4, ease: "easeOut" }}
              className="mt-8 sm:mt-10 flex flex-col sm:flex-row items-start sm:items-center gap-4 sm:gap-6 text-sm text-slate-500 font-medium"
            >
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-brand-orange" />
                <span>{t.hero.noCard}</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-brand-orange" />
                <span>{t.hero.setup}</span>
              </div>
            </motion.div>
          </motion.div>

          {/* Abstract 3D / Chat Visual */}
          <motion.div
            style={{ y: yChat }}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="relative h-[600px] hidden lg:block"
          >
            <div className="absolute inset-0 bg-gradient-to-tr from-brand-soft to-white rounded-[3rem] border border-slate-200/50 shadow-2xl overflow-hidden" dir="ltr">
              <div className="absolute top-0 left-0 right-0 h-16 bg-white/80 backdrop-blur-md border-b border-slate-100 flex items-center px-6 gap-4">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-amber-400" />
                <div className="w-3 h-3 rounded-full bg-green-400" />
              </div>

              <div className="p-8 pt-24 space-y-6">
                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 }}
                  className="bg-white p-4 rounded-2xl rounded-tl-none shadow-sm border border-slate-100 max-w-[80%]"
                >
                  <p className="text-slate-700">{t.hero.chat1}</p>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 1.5 }}
                  className="bg-brand-orange text-white p-4 rounded-2xl rounded-tr-none shadow-md shadow-brand-orange/20 max-w-[80%] ml-auto"
                >
                  <p>{t.hero.chat2}</p>
                  <div className="mt-3 bg-white/20 p-3 rounded-xl backdrop-blur-sm border border-white/10">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <PackageSearch className="w-4 h-4" />
                      <span>{t.hero.synced}</span>
                    </div>
                  </div>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 2.5 }}
                  className="bg-white p-4 rounded-2xl rounded-tl-none shadow-sm border border-slate-100 max-w-[80%]"
                >
                  <p className="text-slate-700">{t.hero.chat3}</p>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 3.5 }}
                  className="bg-brand-orange text-white p-4 rounded-2xl rounded-tr-none shadow-md shadow-brand-orange/20 max-w-[80%] ml-auto"
                >
                  <p>{t.hero.chat4}</p>
                  <div className="mt-3 bg-white p-3 rounded-xl flex items-center gap-3 border border-slate-100 text-brand-black">
                    <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center text-red-500">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="font-semibold text-sm">{t.hero.quoteName}</p>
                      <p className="text-xs text-slate-500">{t.hero.quoteDesc}</p>
                    </div>
                  </div>
                </motion.div>
              </div>
            </div>

            {/* Floating decorative elements */}
            <motion.div
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              className={`absolute ${isRtl ? '-left-8' : '-right-8'} top-32 bg-white p-4 rounded-2xl shadow-xl border border-slate-100 flex items-center gap-3`}
              dir="ltr"
            >
              <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600">
                <Globe2 className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{t.hero.langTitle}</p>
                <p className="font-bold text-sm">{t.hero.langDesc}</p>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
};

const Features = () => {
  const { t } = useTranslation();

  const features = [
    {
      icon: <Globe2 className="w-6 h-6 text-blue-500" />,
      title: t.features.f1Title,
      description: t.features.f1Desc,
      className: "md:col-span-2 bg-gradient-to-br from-white to-blue-50/50"
    },
    {
      icon: <PackageSearch className="w-6 h-6 text-brand-orange" />,
      title: t.features.f2Title,
      description: t.features.f2Desc,
      className: "md:col-span-1 bg-white"
    },
    {
      icon: <Handshake className="w-6 h-6 text-emerald-500" />,
      title: t.features.f3Title,
      description: t.features.f3Desc,
      className: "md:col-span-1 bg-white"
    },
    {
      icon: <FileText className="w-6 h-6 text-red-500" />,
      title: t.features.f4Title,
      description: t.features.f4Desc,
      className: "md:col-span-2 bg-gradient-to-r from-white to-red-50/30"
    }
  ];

  return (
    <section id="features" className="py-16 sm:py-24 bg-white relative">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center max-w-2xl mx-auto mb-12 sm:mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-3 sm:mb-4">{t.features.title}</h2>
          <p className="text-base sm:text-lg text-slate-600">{t.features.desc}</p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6 auto-rows-[minmax(200px,auto)]">
          {features.map((feature, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 40, scale: 0.95 }}
              whileInView={{ opacity: 1, y: 0, scale: 1 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6, delay: index * 0.15, ease: "easeOut" }}
              whileHover={{ y: -5, scale: 1.02, transition: { duration: 0.2 } }}
              className={`p-6 sm:p-8 rounded-[2rem] border border-slate-200 shadow-sm hover:shadow-xl transition-all group ${feature.className}`}
            >
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-white border border-slate-100 shadow-sm flex items-center justify-center mb-4 sm:mb-6 group-hover:scale-110 transition-transform">
                {feature.icon}
              </div>
              <h3 className="text-xl sm:text-2xl font-bold mb-2 sm:mb-3 tracking-tight">{feature.title}</h3>
              <p className="text-sm sm:text-base text-slate-600 leading-relaxed font-light">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

const Integrations = () => {
  const { t } = useTranslation();

  return (
    <section id="integrations" className="py-16 sm:py-24 bg-brand-soft/30 border-y border-slate-200/50 overflow-hidden">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.6 }}
        className="max-w-[1440px] mx-auto px-4 sm:px-6 mb-8 sm:mb-12 text-center"
      >
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-3 sm:mb-4">{t.integrations.title}</h2>
        <p className="text-sm sm:text-base text-slate-600">{t.integrations.desc}</p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1, delay: 0.2 }}
        className="relative flex overflow-x-hidden group"
        dir="ltr"
      >
        <div className="animate-marquee flex whitespace-nowrap items-center gap-8 sm:gap-16 py-4">
          {[...Array(2)].map((_, i) => (
            <React.Fragment key={i}>
              <div className="flex items-center gap-3 sm:gap-4 text-xl sm:text-2xl font-bold text-slate-400 hover:text-brand-black transition-colors">
                <MessageCircle className="w-6 h-6 sm:w-8 sm:h-8 text-[#25D366]" /> WhatsApp
              </div>
              <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-slate-300" />
              <div className="flex items-center gap-3 sm:gap-4 text-xl sm:text-2xl font-bold text-slate-400 hover:text-brand-black transition-colors">
                <Zap className="w-6 h-6 sm:w-8 sm:h-8 text-blue-600" /> Zoho CRM
              </div>
              <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-slate-300" />
              <div className="flex items-center gap-3 sm:gap-4 text-xl sm:text-2xl font-bold text-slate-400 hover:text-brand-black transition-colors">
                <PackageSearch className="w-6 h-6 sm:w-8 sm:h-8 text-indigo-600" /> Zoho Inventory
              </div>
              <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-slate-300" />
            </React.Fragment>
          ))}
        </div>

        <div className="absolute top-0 animate-marquee2 flex whitespace-nowrap items-center gap-8 sm:gap-16 py-4">
          {[...Array(2)].map((_, i) => (
            <React.Fragment key={i}>
              <div className="flex items-center gap-3 sm:gap-4 text-xl sm:text-2xl font-bold text-slate-400 hover:text-brand-black transition-colors">
                <MessageCircle className="w-6 h-6 sm:w-8 sm:h-8 text-[#25D366]" /> WhatsApp
              </div>
              <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-slate-300" />
              <div className="flex items-center gap-3 sm:gap-4 text-xl sm:text-2xl font-bold text-slate-400 hover:text-brand-black transition-colors">
                <Zap className="w-6 h-6 sm:w-8 sm:h-8 text-blue-600" /> Zoho CRM
              </div>
              <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-slate-300" />
              <div className="flex items-center gap-3 sm:gap-4 text-xl sm:text-2xl font-bold text-slate-400 hover:text-brand-black transition-colors">
                <PackageSearch className="w-6 h-6 sm:w-8 sm:h-8 text-indigo-600" /> Zoho Inventory
              </div>
              <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-slate-300" />
            </React.Fragment>
          ))}
        </div>
      </motion.div>
    </section>
  );
};

const Footer = ({ onOpenLegal }: { onOpenLegal: (type: 'privacy' | 'terms') => void }) => {
  const { t } = useTranslation();

  return (
    <motion.footer
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.8 }}
      className="bg-white py-8 sm:py-12 border-t border-slate-200"
    >
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 flex flex-col md:flex-row items-center justify-between gap-4 sm:gap-6">
        <div className="flex items-center gap-2" dir="ltr">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center">
            <img src="/logo.svg" alt="Treejar Logo" className="w-full h-full object-contain" />
          </div>
          <span className="font-bold text-xl tracking-tight">Treejar<span className="text-brand-orange">.AI</span></span>
        </div>

        <div className="flex flex-col items-center gap-1">
          <p className="text-slate-500 text-sm text-center">
            {t.footer.rights}
          </p>
          <p className="text-slate-400 text-xs text-center">
            Разработано <a href="https://aidevteam.ru/" target="_blank" rel="noopener noreferrer" className="hover:text-brand-orange transition-colors font-medium">AI Dev Team</a>
          </p>
        </div>

        <div className="flex gap-4 sm:gap-6 text-sm font-medium text-slate-600">
          <button onClick={() => onOpenLegal('privacy')} className="hover:text-brand-orange transition-colors">{t.footer.privacy}</button>
          <button onClick={() => onOpenLegal('terms')} className="hover:text-brand-orange transition-colors">{t.footer.terms}</button>
        </div>
      </div>
    </motion.footer>
  );
};

const LegalModal = ({ isOpen, onClose, type }: { isOpen: boolean, onClose: () => void, type: 'privacy' | 'terms' | null }) => {
  const { t, lang } = useTranslation();

  if (!isOpen || !type) return null;

  const content = t.legal[type];

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/40 backdrop-blur-sm"
          onClick={onClose}
        />
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-3xl max-h-[85vh] bg-white rounded-3xl shadow-2xl flex flex-col overflow-hidden"
          dir={lang === 'ar' ? 'rtl' : 'ltr'}
        >
          <div className="flex items-center justify-between p-6 border-b border-slate-100 bg-white/80 backdrop-blur-md z-10">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">{content.title}</h2>
              <p className="text-sm text-slate-500 mt-1">{content.lastUpdated}</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 bg-slate-100 text-slate-500 hover:text-brand-black hover:bg-slate-200 rounded-full transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6 overflow-y-auto">
            <div className="space-y-8">
              {content.sections.map((section, idx) => (
                <div key={idx}>
                  <h3 className="text-lg font-bold text-brand-black mb-2">{section.heading}</h3>
                  <p className="text-slate-600 leading-relaxed font-light">{section.text}</p>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default function App() {
  const [lang, setLang] = useState<Language>('en');
  const [legalModal, setLegalModal] = useState<'privacy' | 'terms' | null>(null);

  return (
    <LanguageContext.Provider value={{ lang, setLang }}>
      <div
        className={`min-h-screen selection:bg-brand-orange/20 selection:text-brand-orange ${lang === 'ar' ? 'font-arabic' : ''}`}
        dir={lang === 'ar' ? 'rtl' : 'ltr'}
      >
        <Header />
        <main>
          <Hero />
          <Features />
          <Integrations />
        </main>
        <Footer onOpenLegal={setLegalModal} />

        {legalModal && (
          <LegalModal
            isOpen={!!legalModal}
            onClose={() => setLegalModal(null)}
            type={legalModal}
          />
        )}

        {/* Add custom styles for marquee animation */}
        <style dangerouslySetInnerHTML={{
          __html: `
          @keyframes marquee {
            0% { transform: translateX(0%); }
            100% { transform: translateX(-100%); }
          }
          @keyframes marquee2 {
            0% { transform: translateX(100%); }
            100% { transform: translateX(0%); }
          }
          .animate-marquee {
            animation: marquee 25s linear infinite;
          }
          .animate-marquee2 {
            animation: marquee2 25s linear infinite;
          }
          .font-arabic {
            font-family: 'Cairo', 'Inter', sans-serif;
          }
        `}} />
      </div>
    </LanguageContext.Provider>
  );
}
