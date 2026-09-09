# Creating App Store Screenshot Packs

A Codex skill for turning raw app screenshots into a reviewed, multi-platform marketing pack for Apple App Store and Google Play.

The skill shows an HTML gallery before rendering, lets you select a layout and style, sanitizes private or demo data, checks current official store dimensions, and returns one ZIP containing iPhone, iPad, Android phone, and Android tablet assets.

## المميزات

- معاينة HTML قبل توليد الصور النهائية.
- ثلاثة Layouts: `L1 Hero` و`L2 Split` و`L3 Feature Focus`.
- ثلاثة Styles: `S1 Clean Cream` و`S2 Bold Brand` و`S3 Soft Gradient`.
- إخفاء البريد والبيانات الشخصية وبيانات الدفع والحسابات التجريبية.
- التحقق من أحدث المقاسات من وثائق Apple وGoogle الرسمية وقت التشغيل.
- منع عرض لقطة iPad على أنها واجهة iPhone أو Android بدون موافقتك.
- إخراج PNG مرتبة وملف `manifest.json` داخل ZIP واحد.

## المتطلبات

- Codex يدعم Skills وأدوات إنشاء/تعديل الصور وفتح ملفات HTML.
- Python 3 لتشغيل أداة التحقق والتغليف؛ لا توجد مكتبات Python إضافية مطلوبة وقت الاستخدام.
- اتصال بالإنترنت للتحقق من مقاسات المتاجر الحالية.

## التثبيت

### الطريقة الموصى بها: Git

نفّذ الأمر التالي في Terminal:

```bash
git clone https://github.com/ahmed-khaled-z/creating-app-store-screenshot-packs.git ~/.codex/skills/creating-app-store-screenshot-packs
```

تحقق من وجود ملف المهارة مباشرة في هذا المسار:

```bash
test -f ~/.codex/skills/creating-app-store-screenshot-packs/SKILL.md && echo "Skill installed"
```

ابدأ Task جديدة في Codex إذا لم تظهر المهارة في المحادثة الحالية.

### التثبيت اليدوي

1. نزّل الملف من زر **Code → Download ZIP** في صفحة المستودع.
2. فك الضغط.
3. انقل المجلد إلى:

   ```text
   ~/.codex/skills/creating-app-store-screenshot-packs
   ```

4. تأكد أن `SKILL.md` موجود مباشرة داخل هذا المجلد، وليس داخل مجلد متداخل إضافي.

### التحديث

إذا ثبّت المهارة باستخدام Git:

```bash
git -C ~/.codex/skills/creating-app-store-screenshot-packs pull --ff-only
```

### إزالة المهارة

انقل المجلد التالي إلى سلة المهملات ثم ابدأ Task جديدة في Codex:

```text
~/.codex/skills/creating-app-store-screenshot-packs
```

## الاستخدام

أرفق لقطات الشاشة ثم اكتب:

```text
استخدم $creating-app-store-screenshot-packs لإنشاء حزمة صور للـApp Store وGoogle Play من اللقطات المرفقة.
```

يمكنك إضافة تفاصيل اختيارية:

```text
استخدم $creating-app-store-screenshot-packs.
اسم التطبيق: Schoolz
اللغة: English
استخدم ألوان الشعار المرفق.
اسمح بتكييف لقطات iPad للتابلت Android فقط.
```

## ماذا يحدث أثناء التشغيل؟

1. تفحص المهارة كل لقطة وتحدد المنصة والاتجاه والبيانات التي يجب إخفاؤها.
2. تسألك فقط عن المعلومات الضرورية غير المتوفرة، ومنها السماح بتكييف لقطة لمنصة أخرى.
3. تتحقق من مقاسات Apple وGoogle الحالية من المصادر الرسمية.
4. تنشئ نسخة منخفضة الدقة ومنقحة من لقطة ممثلة، ثم تعرض صفحة `preview.html` محليًا.
5. تختار Layout وStyle وتنسخ كودًا مثل `L2-S1` إلى المحادثة.
6. يبدأ التوليد النهائي بعد تأكيد الكود فقط.
7. تتحقق الأداة من المقاسات والأسماء وبنية PNG ثم تنشئ ملف ZIP.

## شكل ملف ZIP

```text
app-store-assets.zip
└── app-store-assets/
    ├── manifest.json
    ├── iphone/
    │   ├── 01.png
    │   └── 02.png
    ├── ipad/
    ├── android-phone/
    └── android-tablet/
```

يسجل `manifest.json` اللغة والـLayout والـStyle والمقاسات ومصدر كل لقطة والمنصات التي تم تكييفها.

## ملاحظات مهمة

- أفضل نتيجة تأتي من توفير لقطات أصلية لكل منصة وجهاز.
- إذا وفرت لقطات iPad فقط، فلن تعتبرها المهارة واجهة iPhone أو Android أصلية دون موافقتك.
- راجع النصوص التسويقية والادعاءات قبل رفع الصور إلى المتجر.
- المقاسات ليست مخزنة كثوابت داخل المهارة، لأنها قد تتغير؛ يتم التحقق منها وقت التشغيل.

## اختبار المستودع

اختبارات Python:

```bash
python3 scripts/test_package_assets.py
python3 scripts/test_preview_html.py
```

اختبار تزامن اختيارات HTML، ويتطلب Node.js للاختبار فقط:

```bash
node scripts/test_preview_race.js
```

## Repository structure

```text
SKILL.md                  Skill workflow
agents/openai.yaml        Codex display metadata
assets/preview.html       Self-contained layout/style selector
scripts/package_assets.py Deterministic PNG validation and ZIP packaging
scripts/test_*.py         Python regression checks
scripts/test_preview_race.js HTML async-state regression check
```

## License

MIT
