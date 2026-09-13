# MikoV2 ROADMAP REV7

## Faz Durumu
- FAZ 0..5  ✅ (bootstrap + skeleton + implementation)
- FAZ 6     ✅ Integration (100 test)
- FAZ 7     ✅ Chaos (31 test)
- FAZ 8     ✅ Shadow (MEXC live)
- FAZ 9     ⏳ Dashboard + Eksik Modüller (SIRA)
- FAZ 10+   — YOK (son faz)

## Python: 3.10
## Framework: aiohttp.web (backend), aiohttp.ClientSession (client)
## Exchange: MEXC Futures (BTC_USDT format)

## FAZ 9 İş Listesi
1. DB şema genişletme (positions+15, orders+5, 3 yeni tablo)
2. Universe scanner (takip only)
3. micro_trigger
4. Position lifecycle (fill → DB)
5. Dashboard backend
6. Frontend
7. E2E smoke

## Test Sayıları
- unit: 397
- integration: 100
- chaos: 31
- shadow: 5 (mock)
- TOPLAM: 533