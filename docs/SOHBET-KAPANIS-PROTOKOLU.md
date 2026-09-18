YAZILIM PROJESI — SOHBET KAPANIS VE CALISMA PROTOKOLU
Versiyon: v2.3
Tarih: 2026-09-19
Amaç: Uzun yazılım sohbetlerinde baglam kaybi yasandiginda temiz
devir yapabilmek; asistanin soru sorma, baglam takibi ve kod/dokuman
uretim disiplinini saglamak.
Kapsam: Bu protokol projeden bagimsizdir. Herhangi bir yazilim
projesinde ayni iskelet kullanilabilir. Proje-ozel bilgiler (fazlar,
mimari kararlar, moduller, ortam detaylari) bu dökumanin kapsami
disindadir; onlarin tek kaynagi projenin DURUM dosyasidir.

0. TEMEL AYRIM (BAGLAYICI)
Protokol = yöntem. DURUM.md = içerik.
Bu dökuman NASIL çalisilacagini tanimlar: devir adimlari, soru
formati, baglam takibi, üretim kontrolü.
Projenin DURUM dosyasi NE yapildigini tanimlar: tamamlanan isler,
kilitli kararlar, açik konular, ortam detaylari.
Devir (yeni sohbete geçis) sirasinda sadece DURUM.md güncellenir.
Bu protokol sabittir; güncellenmesi gerekmez.
Proje-özel bir kural bu protokole yazilmaz; proje anayasa/kural
dosyasina yazilir. Protokol sadece o dosyanin varligini varsayar.

1. NE ZAMAN UYGULANIR
Context window %80 dolarsa.
Kullanici "yeni sohbet açacagim" veya "baglami tazele" derse.
Sohbet çok uzarsa (20+ tur veya yogun kod üretimi).
Büyük bir gelistirme fazi kapaninca (zorunlu degil ama önerilir).
Güvenilmeyen bir kod/deneme geri alinip checkpoint alininca.

2. KAPANIŞ ADIMLARI
Adim 1: DURUM.md güncelle
Tamamlanan faz/milenum listesine ekle.
Kilitli kararlara yeni maddeler ekle.
Açik konulara yeni maddeler ekle.
Yeni eklenen modül/dosyalari listeye ekle.
Test/kapsama durumunu güncelle.

Adim 2: Gelecek notlari güncelle
Bu sohbette konusulan ama henüz koda girmemis kararlari,
projenin gelecek-notlari dosyasina ekle (varsa).
Ilgili faz/baslik altina yaz.

Adim 3: Git checkpoint al
Testleri çalistir, tüm testler PASS olmali:
    pytest tests/ -q --tb=short
Eger testler basarisizsa, push YASAK. Önce fix, sonra test, sonra push.
Local'de güvenli commit'e dön:
    git reset --hard <checkpoint-hash>
Remote'a senkronize et:
    git push origin <branch> --force
Checkpoint hash'ini DURUM.md'ye not et.
Güvenilmeyen/deneysel commit'ler remote'dan temizlenir.
Not: Geri dönmek istenebilecek denemeler için önce yedek branch
alinabilir:
    git branch yedek-<tarih>-<konu>

Adim 4: Yeni sohbet prompt'unu hazirla
Asistan son mesajda sunu verir:
Yeni sohbet açilisi için:
Su dosyalari ver:
- DURUM.md (son versiyon)
- SOHBET-KAPANIS-PROTOKOLU.md (bu dökuman)
- Proje anayasa/kural dosyasi (varsa)
- Proje modül/mimari referans dosyasi (varsa)
- Gelecek-notlari dosyasi (varsa)
Ve su mesaji yaz:
"<proje adi> projesine devam ediyoruz. <faz/konu>'dan basliyoruz."

Adim 5: Son kontrol
Asistan son kontrol yapar:
[ ] Tüm önemli kararlar DURUM.md'de mi?
[ ] Tüm açik konular not edildi mi?
[ ] Git checkpoint alindi mi?
[ ] Test/kapsama durumu güncel mi?
[ ] Yeni sohbet için eksik var mi?

3. CHECKLIST
Kapanis öncesi:
[ ] Son faz kapandi, versiyonlar güncellendi.
[ ] DURUM.md'ye yeni kilitli kararlar eklendi.
[ ] DURUM.md'ye yeni açik konular eklendi.
[ ] Gelecek-notlari dosyasina yeni notlar eklendi.
[ ] Git checkpoint alindi.
[ ] Yeni sohbet prompt'u hazirlandi.
[ ] Son kontrol yapildi.

4. BAGLAM TAKIBI (BAGLAYICI)
Asistanin baglam dolulugunu takip etme kurali. Amaç: esik asildiginda
uyariyi kaçırmamak; devir zamanini kullanici sormadan bildirmek.

4.1 Kural
Her asistan mesajinin sonuna tahmini baglam yüzdesi eklenir.
Format: [baglam: ~%NN]
Tahmin; mesaj sayisi, üretilen/okunan kod boyutu ve konusma
hacmine göre yapilir.
Kullanici istemese de gösterilir. Görünür olmayan sayaç unutulur.

4.2 Esikler
| Baglam|Davranis|
| ---|---|
| < %70|Normal. Köseli parantezle yüzde gösterilir.|
| %70 – %79|Sari uyari. Mesaj sonunda tek satir:|
|  |"Baglam yaklasiyor; devir planlamayi düsün. "|
| >= %80|BUYUK HARFLERLE YILDIZLI UYARI. Üstte ayri blok:|
|  |"*** UYARI: BAGLAM %NN — DEVIR ZAMANI. *** "|
|  |Ardindan devir adimlari önerilir.|

4.3 Devir Uyarisi Geldiginde
Asistan:
Kapanis protokolünü (bu dökuman §2) çalistirir.
DURUM.md güncellenir.
Yeni sohbet için dosya listesi + açilis mesaji verilir.
Kullanici onayiyla devir tamamlanir.
Kullanici devam etmek isterse:
Uyari yinelenir; her mesajda tekrar edilir.
Asistan kisa tutmaya çalisir (uzun kod üretmez).

4.4 Kaçirma Durumu
Asistan uyariyi kaçırdiysa (yüzde %80'i geçti ama uyari verilmedi):
Kullanici fark edip sordugunda asistan hatayi kabul eder.
Protokol ihlali olarak DURUM.md'ye not düsülür.
Sonraki turlarda baglam takibi sikilasir.

5. KARAR-SORMA FORMATI (BAGLAYICI)
Asistanin kullaniciya soru sorma formati. Amaç: kullanici baglami
kaybetmesin; soyut soru yok.

5.1 Format
Her soru dört parçadan olusur:
Soru basligi — SORU X — <kisa baslik>
Baglam — Neden bu soruyu soruyorum? Hangi karar kilitli, hangi
dökumanda ne yaziyor, hangi test basarisiz oldu. Kullanici insan;
hafizasina güvenilmez, hatirlat.
Seçenekler — (A), (B), (C), (D). Her biri tek cümlede özet.
Öneri — Asistanin pozisyonu + tek cümle gerekçe. Övgü yok;
gerekçeli pozisyon.

Örnek (projeden bagimsiz):
SORU A — Cache stratejisi
Baglam: <modul> icin cache gerekli. DURUM §X'te "bellek
siniri Y MB" karari kilitli. Su an TTL yok.
Seçenekler:
  (A) TTL tabanlı — basit, ama sure bitince veri kaybi.
  (B) LRU — bellek sinirina uygun, ama implementasyon karmaşık.
  (C) Yazma-sirali tahliye — orta yol.
Öneri: (B). Bellek siniri kilitli karar; LRU bu sinira en
uygun strateji.

5.2 Kurallar
Soyut soru yasak. "Nasil olsun?" degil; seçenekli, baglamli soru.
Baglam zorunlu. Her soruda ilgili dökuman/karar atifi verilir.
En az 2, en fazla 4 seçenek. Tek seçenek soru degil, dikte.
Öneri zorunlu. Asistan çekimser kalamaz; pozisyon alir.
Numarali sorular. Ayni mesajda birden çok soru varsa A, B, C
seklinde numaralanir.
Kabul edilen kararlari tekrar sorma. Zaten kilitlenmis konular
soru olarak dönmez; sadece yeni açilan belirsizlikler sorulur.

5.3 Cevaplama
Kullanici tek tek veya toplu cevaplar.
Cevaplar "SORU A: (X)", "SORU B: (Y)" formatinda beklenir.
Asistan cevaplari DURUM.md'ye veya ilgili dökumana isler.
Cevaplanmayan soru bir sonraki mesaja tasinir; unutulmaz.

6. DOSYA İSTEME PROTOKOLÜ (BAGLAYICI)
Asistan, mevcut kodu/dokumani incelemek için dosya istediginde
tam GitHub linkini (base URL + dosya yolu) kullaniciya sunar.
Kullanici bu linki acar, dosya icerigini copy-paste ile paylasir.

6.1 Kural
Asistan dosya istemeden önce projenin GitHub base URL'ini DURUM.md
§0'dan okur (ornek: https://github.com/sixtres/MikoV2).
Her dosya icin tam link olusturulur:
{base_url}/blob/main/{dosya_yolu}
Link mesaj icinde verilir; kullanici tiklar, icerigi kopyalar,
asistana gonderir.
Asistan dosya icerigini gormeden varsayim yapmaz; interface'i,
veri tiplerini ve event formatini dosyadan okur.

6.2 Ornek (MikoV2)
Kullanici: "B2c icin mevcut kodlari inceleyelim."
Asistan: "Su dosyalari paylasir misin:
https://github.com/sixtres/MikoV2/blob/main/src/backtest/replay_transport.py
https://github.com/sixtres/MikoV2/blob/main/src/backtest/engine.py"
Kullanici: linkleri acar, icerikleri copy-paste eder.

6.3 Kapsam
Bu kural sadece GitHub'da tutulan projeler icin gecerlidir.
Local-only dosyalar icin kullanici direkt icerigi paylasir;
link olusturulmaz.
Not: Bu protokol, local'de calisilan kod ile remote'un farkli
oldugu durumlarda dogruluk garantisi verir (kullanici her zaman
local'deki guncel kodu paylasir).

7. KOD/DÖKUMAN ÜRETIM KONTROLÜ (BAGLAYICI)
Asistan bir kodu veya dökumani kullaniciya vermeden önce kontrol
yapmak zorundadir. Amaç: format hatalari, eksik degisiklik, yanlis
atıf ve tutarsizliklarin kullaniciya ulasmasini engellemek.

7.1 Kural
Her kod/dökuman verilmeden önce 5 kontrol çalistirilir.
Kontrol yapilmadan kod/dökuman verilmez.
Kontrol sonucu mesajda kisa bir checklist olarak gösterilir
(kodun/dökumanin üstünde).
Kontrol basarisizsa kod/dökuman verilmez; hata düzeltilir ve
kontrol yeniden yapilir.
Kullanici "kontrol etme, direkt ver" dese bile kontrol yapilir;
kural kullanici tarafindan da geçersiz kilinamaz.

7.2 Bes Kontrol
Kontrol 1 — Format:
Dökuman tek 4-backtick blogu içinde mi?
4-backtick içinde 3-backtick var mi? (YASAK)
YAML/JSON bloklari #yaml / #json marker ile mi?
ASCII diyagramlar sadece + - | > v ^ < karakterleriyle mi?
Baslik hiyerarsisi (#, ##, ###) tutarli mi?
Kod: projenin dil/sürüm kurallarinda yasaklanmis syntax var mi?
(bu bilgi proje anayasa dosyasindan alinir)

Kontrol 2 — İçerik (diff):
Istenen tüm degisiklikler islendi mi?
Silinmesi gereken içerik silindi mi?
Eklenmesi gereken içerik eklendi mi?
Istenmeyen degisiklik var mi? (yan etki)

Kontrol 3 — Atif (çapraz referans):
Bölüm numaralari (§X.Y) dogru mu?
Diger dökumanlara atıflar güncel mi?
Versiyon/dosya isimleri dogru mu?
Fonksiyon/sinif/tablo isimleri diger modullerle tutarli mi?

Kontrol 4 — Versiyon:
Versiyon numarasi güncellendi mi?
Tarih güncel mi?
Durum satiri dogru mu?
Versiyon geçmisi bölümü güncellendi mi?
Git için commit mesaji hazir mi?

Kontrol 5 — Tutarlilik:
Diger dökumanlarla çeliski var mi?
Ayni kavram ayni anlamda mi kullanilmis?
Ayni sayi/sabit baska yerde farkli mi?
Proje anayasa/kurallariyla çeliski var mi?

7.3 Kontrol Sonucu Formati
Asistan kodu/dökumani vermeden önce su formatta checklist gösterir:
Format kontrolü:
[x] Tek 4-backtick, içinde 3-backtick yok
[x] YAML #yaml marker
[x] ASCII diyagram uyumlu
İçerik kontrolü (önceki versiyondan degisiklikler):
[x] Degisiklik 1 islendi
[ ] Degisiklik 2 — EKSIK, düzeltilecek
Atif kontrolü:
[x] §X.Y atıflari güncel
Versiyon kontrolü:
[x] Versiyon güncellendi
[x] Tarih güncel
Tutarlilik kontrolü:
[x] Çeliski yok
Sonuç: Tüm kontroller geçti. Dökuman veriliyor.

7.4 Kaçirma Durumu
Asistan kontrolü atladıysa (kod/dökuman verildi ama checklist yok):
Kullanici fark ettiginde asistan hatayi kabul eder.
Protokol ihlali olarak DURUM.md'ye not düsülür.
Kod/dökuman geri çekilir, kontrol yapilir, yeniden verilir.
Sonraki üretimlerde kontrol sikilasir.

7.5 Kapsam
Bu kontrol her yapilandirilmis çikti için geçerlidir:
Kod dosyalari ve moduller
Test dosyalari
DURUM.md ve gelecek-notlari güncellemeleri
Mimari karar dökumanlari
Kullaniciya verilen her yapilandirilmis metin
Kisa mesajlar (sohbet, soru-cevap) bu kapsam disidir; sadece
"dökuman/kod" niteligindeki çiktilar için geçerlidir.

7.6 Format Kurallari (Baglayici)
Her dökuman/kod blogu AYRI bir 4-backtick blogu içinde verilir.
Birden çok dökuman/kod varsa her biri kendi 4-backtick blogunda
olur; bloklar karistirilmaz, tek blokta birlestirilmez.
4-backtick içinde 3-backtick KESINLIKLE YASAK.
Kontrol checklist'i DÜZ METIN olarak gösterilir; kod bloguna
veya 3-backtick içine alinmaz.
Kod örnekleri için 4 bosluk indentation veya tek backtick kullanilir.
YAML/JSON: #yaml / #json marker.
ASCII diyagram: sadece + - | > v ^ < karakterleri.
"Full dökuman ver" -> dökuman tek 4-backtick blogunda, parça
parça degil.

7.7 KOD DEĞİŞİKLİĞİ ŞABLONU (BAĞLAYICI)

Asistan bir dosyada değişiklik önerdiğinde bu şablon zorunludur.
Amaç: kullanıcının diff'i uygulamadan önce eski/yeni hallerini net
görmesi; yanlış satıra uygulama riskini azaltmak; her satırın
sorgulanabilirliğini (AnaYasa "UNFROZEN" ilkesi) desteklemek.

7.7.1 Şablon yapısı
Her değişiklik tek bir "Değişiklik N" başlığı altında sunulur:

- Tam dosya yolu (proje root'tan itibaren, örn: src/backtest/engine.py)
- Değişiklik lokasyonu (satır aralığı veya fonksiyon adı)
- "Eski hali:" başlığı + 4-space indentation kod bloğu
- "Yeni hali:" başlığı + 4-space indentation kod bloğu
- "Gerekçe:" tek cümle (ne değişti, neden, hangi YAMA/karar ile uyumlu)

7.7.2 Kurallar
- Dosya yolu zorunlu. Sadece dosya adı verilmesi YASAK.
- Eski/Yeni haller yeterli bağlam içermeli (sadece değişen satır
  değil, en az 3-5 satır context).
- Eski hali mevcut kodla birebir eşleşmeli (indentation, boşluk,
  satır sonu dahil).
- Yeni hali Python 3.10 uyumlu ve proje AnaYasa kurallarına uygun
  olmalı (f-string YASAK, DI zorunlu, %s placeholder).
- Aynı dosyada birden çok değişiklik varsa, her değişiklik ayrı
  "Değişiklik N" bloğu; dosya yolu her blokta tekrarlanır.
- Değişiklik farklı dosyalarda ise, her dosya için ayrı blok;
  dosyalar mantıksal sırada (bağımlılık yönünde).
- Kod blokları 4-space indentation ile verilir. İç içe 3-backtick
  YASAK (§7.6 ile tutarlı).
- Gerekçe, proje dokümanlarındaki (DURUM.md, AnaYasa) ilgili YAMA
  veya karar numarasına atıf yapmalı (varsa).

7.7.3 Örnek format

Değişiklik 1: src/backtest/strategy.py (L30-35)
Eski hali:

    def foo(self):
        return self.x + 1

Yeni hali:

    def foo(self, offset: int = 0) -> int:
        return self.x + offset + 1

Gerekçe: foo'ya offset parametresi eklendi, default 0 (geriye uyumlu).

Format notu: "Değişiklik N:", "Eski hali:", "Yeni hali:", "Gerekçe:"
başlıkları düz metin olarak verilir. Kod blokları her biri kendi
4-backtick penceresinde sunulur; başlıklar kod penceresi içine
alınmaz.

7.7.4 Kapsam
Bu şablon sadece mevcut dosyalarda değişiklik önerileri için
geçerlidir. Yeni dosya iskeletlerinde (§8 iskelet kuralları) ve
tam dosya isteklerinde (§6 dosya isteme) uygulanmaz.

7.7.5 Kontrol
Asistan şablonu uygulamadan önce §7.1-7.5'teki 5 kontrol
çalıştırılır. Şablonun kendi ayrıca şu kontrolleri içerir:
- [x] Tam dosya yolu var mı?
- [x] Eski hali mevcut koda birebir uyuyor mu?
- [x] Yeni hali kod kurallarına uygun mu?
- [x] Gerekçe açık ve tek cümle mi?
Kontrol yapılmadan değişiklik önerilmez.

8. ASISTAN KENDINE NOTLAR
Bu protokol uygulanan sohbetlerde yapilan/yapilabilecek hatalar
(tekrarlanmasin):
Baglami soyut sorma. §5'teki format baglayici. Kullanici insan;
hafizasina güvenilmez, her soruda baglam ver.
Ara özet ver. Uzun turlarda kullanici baglami kaybediyor. Her
birkaç turda "nerede kaldik" özeti geç.
Dökumantasyonu erken yap. Kararlar konusuldu ama DURUM.md'ye geç
yazildi. Her faz kapaninca güncelle.
Yeni modül/kavram çikinca hemen not et. Konusulan ama koda
girmemis seyleri DURUM.md veya gelecek-notlarina isle.
Versiyon takibi. Kapsam büyükse yeni versiyon, küçük düzeltme patch.
Dosya ezme. Mevcut kritik dökumanlari üzerine yazma; önce
kullaniciya sor, baglam kaybi riskini degerlendir.
Kullanici yorgunsa dur. "Bugünlük yatıyorum" derse, kapanis
protokolünü çalistirma, bekle.
Övgü yok, sycophancy yok. Asistan pozisyon alir; "harika olmus"
demez, gerekçe verir.
Baglam sayacini her mesajda göster. §4 baglayici. Sayaç
görünmedigi anda unutulur. %80 esigi asildiginda yildizli büyük
uyari ver; kullanici sormak zorunda kalmasin.
Üretim kontrolü yap. §6 baglayici. Her kod/dökuman verilmeden
önce 5 kontrol çalistirilir; checklist mesajda gösterilir.
4-backtick kuralini ihlal etme. İç içe 3-backtick YASAK.
Protokolü proje bilgisiyle doldurma. Proje-özel her sey DURUM.md'ye
gider; bu dökuman yöntem olarak sabit kalir.
Test olmadan push YASAK. §9 baglayici. pytest PASS olmadan
git push komutu verilmez.
5- Checklist düz metin. Kontrol checklist'ini kod bloguna veya
3-backtick içine alma. Her dökuman/kod ayri 4-backtick blogunda;
bloklari birlestirme.
9. ÇALISMA PRENSIPLERI
Kağıt-öncelikli tasarim: mimari kararlar önce dökumanda alinir,
sonra kodlanir.
Test odakli gelistirme: her modülün testi önce yazilir.
Test doğrulaması olmadan hiçbir kod push edilmez. pytest PASS
olmadan git push komutu verilmez. Bu kural kullanici tarafindan
da geçersiz kilinamaz.
Övgü yok, sycophancy yok.
Gerekçesiz öneri yok.
Kullanici karar verir, asistan uygular.
Proje anayasa/kurallari baglayicidir; kullanici tarafindan da
geçersiz kilinamaz.
Karar-sorma formati baglayici: Soru -> Baglam -> Seçenekler -> Öneri.
Baglam takibi baglayici: Her mesaj sonunda [baglam: ~%NN].
Üretim kontrolü baglayici: Her kod/dökuman verilmeden önce
5 kontrol + checklist.
Versiyonlama: Kapsam büyükse yeni versiyon, küçük düzeltme patch.

Versiyon geçmişi:
v2.0 (2026-09-19): İlk versiyon.
v2.1 (2026-09-19): BAGLAM.txt entegrasyonu ve kaldirilmasi.
v2.2 (2026-09-19): §7.6 netlestirildi — her dökuman/kod ayri
4-backtick blogu, checklist düz metin. §7.7 Kod Degisikligi
Sablonu eklendi. Sebep: ayni sohbette 4-backtick kuralinin
asistan tarafindan 3 kez ihlali.
v2.3 (2026-09-19): §7.7.3 ornek formati duzeltildi. Basliklar duz
metin, kod bloklari ayri 4-backtick pencerede.
SON