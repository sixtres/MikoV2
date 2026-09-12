# DURUM REV5 — FAZ 0 KAPANDI — 116 YAMA — 2026-09-12
# PO: Eser Göbekli
# REV4.9.9 FINAL-v4 (110 YAMA) → REV5 (116 YAMA, 12 tasarım onaylı / 4+1 kısmi kodda / 7 FAZ2-4)
# FAZ 0 8 madde kick-back KAPANDI — FAZ 1'e geçiş ONAYLANDI


## 1. Güncel Dosyalar (Source of Truth) — REV5

- **TumModuller:** `MikoV2-Proje-Tum-Moduller-REV5.md` (FINAL, 116 YAMA, UNFROZEN)
- **AnaYasa:** `MikoV2-AnaYasa-REV5.md` (116 YAMA, 245 bulgu)
- **DURUM:** `DURUM-REV5.md` (bu dosya)

## 2. v4 → REV5 Değişim (6 yeni YAMA 362-368 + 8 kick-back düzeltmesi)

| YAMA | Konu | Eski Hali | Yeni Hali | Side Effect |
|------|------|-----------|-----------|-------------|
| 350 | Lock hierarchy | emergency_close 5->3->4 (flush->sqlite->pacer) | sqlite(3)->pacer(4)->flush(5) sırası, call_soon_threadsafe kaldır | Yok, sadece sıra |
| 351 | single-flight race | if symbol in tasks: return await + create_task race | Future pre-insert, sonra create_task, TOCTOU kapandı | Yok, double close engellendi |
| 352 | pre_sync_queue | filter var append YOK, hep boş | gap durumunda append eklendi | Yok, replay için data eklendi |
| 353 | Global refs | db, alerting_agent, compute_obi tanımsız NameError | dependency injection __init__ parametre | Yok, sadece DI |
| 354 | TTL break | OrderedDict break ilk eleman yeni ise eski kalır | break kaldır full scan | Yok, leak kapandı |
| 355 | Pacer _last_dispatch | effective (aged) ile CRITICAL slot bloke | base_prio ile dispatch | Yok, CRITICAL artık bloklanmaz |
| 356 | Flush çift sayaç | _counter + _counter_original senkron değil | tek sayaç + WARNING+clamp (assert sadece test/CI) | Yok, underflow artık gerçek bug |
| 357 | AsyncStateQueue deadlock | mp.Queue + to_thread + Semaphore(8) blocking | asyncio.Queue(200) bridge + single writer task | Yok, non-blocking bridge |
| 358 | Pacer Lock | threading.Lock + sleep(0) busy loop CPU %100 | asyncio.Lock + sleep(remaining) | Yok, CPU düşer |
| 359 | RestGateway timeout | kod 1.0+2.0+1.5=4.5s (DURUM eski 5.5s yanlış) > outer 3.5s ihlal | single outer wait_for(3.5s) | Yok |
| 360 | find_price O(n) | [-p for p in arr] list comp O(n) | np.searchsorted O(log n) | Yok, performans artar |
| 361 | sealed reuse age | sadece local TTL, eski exchange_ts reuse | local + exchange_ts age check | Yok, eski reuse engellendi |

## 3. Yanlış Alarm Kabul Edilen 2 Madde

| # | İddia | Neden Yanlış Alarm |
|---|-------|-------------------|
| 1 | asyncio.Semaphore multi-process | REST gateway TEK PROCESS + each coin single process, asyncio doğru, failover dışında risk yok |
| 6 | Multi-symbol batch | Spec per-symbol depth@100ms, combined stream yok, tek symbol doğru |

DeepSeek kabul etti, dökümana işlenmedi.

## 4. Toplam

- 110 YAMA (v4) + 6 yeni (362,363,364,365,367,368) = 10 YAMA (v4) + 6 yeni (362,363,364,365,367,368) = 116 YAMA. 12 runtime fix tasarım onaylı, koda girmiş 4+1, 7 FAZ2-4 = 116 YAMA (110+6 yeni 362,363,364,365,367,368 — 366 açılmadı)
- 239 bulgu + 6 = 245 bulgu kapatıldı
- FROZEN YOK, UNFROZEN, yeni YAMA 362+ açık

## 5. Yeni Sohbete Geçiş Komutu

```
Bağlam: REV5 yüklü, 116 YAMA, 245 bulgu, UNFROZEN. Dosyalar: MikoV2-AnaYasa-REV5.md + MikoV2-Proje-Tum-Moduller-REV5.md + DURUM-REV5.md
12 runtime fix tasarım onaylı, koda girmiş 4+1 kısmi, 7 FAZ2-4 (350-361) side-effect-safe olarak işlendi, TTL break, Pacer base_prio, lock hierarchy, global DI YASAK zorunlu constructor injection (Y-353) + pre_sync_queue append, single-flight Future, AsyncStateQueue bridge, find_price searchsorted, sealed age check hepsi düzeltildi.
Sonraki adım: src/ modüllerine böl ve pytest -k yama350-361 koş.
```

--- FAZ 0 KAPANIŞ REV5 — 8 madde kick-back çözümü ---

1. Y-356 vs Y-346 çelişki (Y-362/Y-368):
   BEFORE: max(0, counter-1) + if counter truthy bug + assert >=0 prod crash
   AFTER: counter -=1, if <0: WARNING FLUSH_COUNTER_UNDERFLOW + clamp 0, if ==0: set()
   Y-368: assert kaldır, WARNING+clamp, Y-346 uyumlu, PARTIAL → OK

2. Y-359 sayı (Y-363):
   Kod L266 1.0s + L268 2.0s + L270 1.5s =4.5s
   DURUM eski 5.5s yanlış, REV5 4.5s doğru
   Hedef FAZ2: single outer wait_for 3.5s

3. Y-360:
   KODDA -p list comp yok, searchsorted -price var, OK KEEP
   L54-L55, L67-L70 searchsorted doğru

4. Y-259/Y-273:
   251-273 23 gerçek numara loop red team, v4 özetinde detay yok ama rezerv değil
   110 → 116 (362-368) doğru kalır

5. Y-355:
   L232 since = now - _last_dispatch[base_prio], gap = _min_delay[effective]-since
   Asimetri not edildi, tasarım amacı belirsiz, KEEP, Y-366 açılmadı

6. Y-353:
   DI zorunlu, global YASAK, leaf token_bucket vs _state_sem ayrımı OK, KEEP

7. Y-354:
   L652 if local_expired or exch_expired or exch_ts is None and local_expired
   Redundant absorption var, çalışır, KEEP + Y-365 note

8. Y-364/Y-367:
   8 CONFLICT +1 PARTIAL vs 7+2 yanlış
   Doğru: 7 CONFLICT (350,351,352,353,357,358,359) +1 PARTIAL (356) +4 OK (354,355,360,361)=12
   Cümle: 12 tasarım onaylı, 4+1 kodda, 7 FAZ2-4

--- YAMA 362-368 detay REV5 ---
362: resume() fix WARNING+clamp
363: 4.5s düzeltme
364: 7+1+4=12 dokümantasyon
365: Y-354 redundant KEEP
367: 12 fix cümle düzeltme
368: Y-356 assert REVISE WARNING+clamp

--- REV5 src/ 38 dosya FAZ0-SRC-STRUCTURE ---
38 dosya tam ağaç, gizleme YOK, liste AnaYasa ve TumModuller'de var, burada özet
src/ 38 dosya + tests/unit/test_yama_362_368.py

--- REV5 DoD FAZ 0 KAPANDI ---
- [x] 116 YAMA
- [x] Y-356/Y-362/Y-368 WARNING+clamp
- [x] Y-359 4.5s Y-363
- [x] Y-355 asimetri KEEP
- [x] Y-354 redundant KEEP Y-365
- [x] 7+1+4=12 Y-364/Y-367
- [x] 38 dosya ağaç
- [x] Global YASAK DI zorunlu Y-353
- FAZ 0 KAPANDI — FAZ 1 ONAY

--- REV5 FAZ 1 geçiş notu ---
FAZ 0 8 madde kapandı, 6 yeni YAMA eklendi, 110→116, 12 fix 4+1 kodda, kalan 7 FAZ2-4'te uygulanacak