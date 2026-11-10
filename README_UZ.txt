KAMERA KATALOGIM — 4 XONALI PIN-KODLI BULUTLI VERSIYA
======================================================

SAYT QANDAY ISHLAYDI?
- Saytga kirishda faqat 4 xonali PIN-kod so'raladi. Gmail/email yoki Google login yo'q.
- PIN-kod serverda saqlanadi; HTML/JavaScript ichida ko'rinmaydi.
- PIN 5 marta noto'g'ri kiritilsa, kirish 15 daqiqaga bloklanadi.
- Kirgan qurilmada sessiya 30 kun saqlanadi (Chiqish tugmasi bilan yakunlash mumkin).
- Kamera rasmlari, modellari, izohlari va narxlari Supabase bulutida saqlanadi.
- Telefon va kompyuter bir xil bazani ko'radi; ochiq turgan sahifa 15 soniyada yangilanadi.
- Faqat Render serveri Supabase maxfiy service-role kalitiga ega bo'ladi.

MUHIM XAVFSIZLIK ESLATMASI
4 xonali PIN qulay, lekin kuchli parol darajasida emas (10 000 kombinatsiya).
5 urinish / 15 daqiqa cheklovi qo'yilgan. Katalogda juda maxfiy ma'lumot saqlamang.
Agar kuchliroq himoya kerak bo'lsa, keyin PINni 6-8 raqamga oshiramiz.
PINni ChatGPTga yoki boshqa odamga yubormang; uni faqat Render Environment bo'limiga o'zingiz kiriting.

1-QADAM. SUPABASE LOYIHA OCHISH
1. https://supabase.com saytiga kiring va o'zingiz uchun loyiha oching.
2. Project nomi: kamera-katalogim.
3. Database password yarating va o'zingizda saqlang.
4. Region sifatida mavjud bo'lgan yaqin regionni tanlang.
5. Loyiha tayyor bo'lishini kuting.

2-QADAM. DATABASE VA RASM OMBORINI SOZLASH
1. Supabase loyihasini oching -> SQL Editor -> New query.
2. Shu papkadagi supabase_setup.sql faylini oching.
3. Barcha SQL matnini nusxalab SQL Editor ga joylang va Run bosing.
4. Xatolik bo'lmasa, cameras jadvali va private camera-photos ombori tayyor.

3-QADAM. SUPABASE SERVER KALITLARINI OLISH
1. Supabase -> Project Settings -> API Keys (yoki API) bo'limiga kiring.
2. Project URL ni nusxalang.
3. Secret key (yoki eski loyihalarda service_role secret) ni oling.
4. Bu kalit maxfiy: uni hech qachon index.html ga, GitHubga yoki chatga joylamang.
5. Faqat Render -> Environment Variables ichiga kiriting.

4-QADAM. GITHUB REPOSITORY YARATISH
1. https://github.com saytida yangi repository yarating: kamera-katalogim.
2. ZIP faylni kompyuterga oching.
3. Ichidagi quyidagi fayllarni repository ning asosiy qismiga yuklang:
   - app.py
   - index.html
   - requirements.txt
   - render.yaml
   - supabase_setup.sql
   - README_UZ.txt
4. GitHub repository Private bo'lishi mumkin. Render ulash uchun o'z GitHub hisobingizga kirasiz.

5-QADAM. RENDER DA WEB SERVICE YARATISH
1. https://render.com saytiga kiring va GitHub bilan ulang.
2. New -> Web Service ni tanlang.
3. kamera-katalogim repository sini tanlang.
4. Runtime: Python 3.
5. Build Command: pip install -r requirements.txt
6. Start Command: uvicorn app:app --host 0.0.0.0 --port $PORT
7. Instance type: Free (agar mavjud bo'lsa).
8. Environment Variables bo'limiga quyidagi 4 ta qiymatni kiriting:

   SUPABASE_URL = Supabase Project URL
   SUPABASE_SERVICE_ROLE_KEY = Supabase Secret/service_role key
   KATALOG_PIN = o'zingiz tanlagan 4 ta raqam (masalan, bu yerga haqiqiy PIN yozmang)
   SESSION_SECRET = uzun tasodifiy maxfiy matn

SESSION_SECRET yaratish uchun Windows PowerShell yoki CMD da Python bo'lsa:
   python -c "import secrets; print(secrets.token_urlsafe(48))"
Chiqqan qiymatni Render Environment ga kiriting.
9. Deploy tugashini kuting. Render bergan https://....onrender.com manzilini oching.

6-QADAM. TELEFON VA KOMPYUTERDA ISHLATISH
1. Render bergan bir xil sayt manzilini kompyuterda Chrome da oching.
2. O'zingiz belgilagan 4 xonali PIN ni kiriting.
3. Telefonda ham shu manzilni ochib, o'sha PIN ni kiriting.
4. Har bir qurilmada PIN bir marta kiritiladi; sessiya 30 kun saqlanadi.
5. Kamera qo'shing. Ikkinchi qurilmadagi ochiq katalog 15 soniya ichida yangilanadi.
6. Telefon brauzerida menyu -> Add to Home Screen orqali bosh ekranga qo'shishingiz mumkin.

KATALOGDAN FOYDALANISH
- Kamera qo'shish: model, brend, turi, narx, valyuta, izoh va rasm.
- Tahrirlash: narx yoki xususiyatni o'zgartirish.
- O'chirish: kamerani va unga tegishli rasmni bulutdan o'chirish.
- Zaxira: barcha kamera ma'lumotlari va rasmlarini JSON faylga eksport qilish.
- Eski bazani yuklash: oldingi katalogdan olingan JSON zaxirasini import qilish.

ESLATMA
- Internet bo'lishi shart.
- Render bepul xizmatlarida uzoq vaqt ishlatilmaganda server uxlab qolishi mumkin; keyingi ochilish sekinroq bo'lishi mumkin.
- Render va Supabase tariflari/limitlari o'zgarishi mumkin.
- Serverda service-role key borligi uchun GitHub repository ga maxfiy qiymatlarni yozmang.
