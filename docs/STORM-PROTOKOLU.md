# STORM-PROTOKOLÜ
Dosya: STORM-PROTOKOL.md (SSOT)
Sahip: PO (Eser Göbekli)
Amaç: Proje kararlarını çoklu bağımsız LLM ile doğrulama
      (bias-free, kanıt zorunlu, izlenebilir).

Uygulama: PROTOKOL.md §0.7 bu protokole atıf yapar. Bu dosya
kendi kendine yeterlidir; PROTOKOL.md'den bağımsız içerik taşır.

## 0. NE / NEDEN / NASIL
Ne: Bir SORU setini N bağımsız ajana sor, ağırlıklı oyla sentezle.
Neden: Tek ajan bias, kör nokta, izlenebilirlik eksikliği.
Nasıl: Aşama 1 (prompt hazırlığı) → Aşama 2 (ajanlar) → Aşama 3
       (ağırlıklı sentez) → Aşama 4 (PO nihai karar).

## 1. TEMEL İLKELER
1.1 Bias-free: Ajanlara asistan önerisi/cevabı VERİLMEZ.
    Asistan kendi oyunu §2 ağırlığıyla verir; oyun bağımsız
    kanıta dayanır.
1.2 Kanıt zorunlu: evidence_type ∈ {sandbox_test, code_review,
    logical_reasoning, prior_experience, external_doc}.
    sandbox_test → setup + gözlem detayı zorunlu.
1.3 Kimlik zorunlu: family + model + self_reported=true.
1.4 Format zorunlu: cevap tek 4-backtick kod bloğu; dil
    işaretleyicisi YOK; JSON şemasına uyar.
1.5 prompt_version + prompt_version_acknowledged zorunlu.
1.6 Ağırlık tablosu kalibre edilir; PO değiştirir.
1.7 Şeffaflık: her round sonucu DURUM.md'ye; azınlık ayrıca.

## 2. AĞIRLIK TABLOSU
| Ajan (family) | Model | Ağırlık |
|---|---|---|
| Anthropic (asistan) | claude-sonnet-4.5 | 1.25 |
| OpenAI | gpt-5 | 1.00 |
| Google | gemini-2.5-pro | 1.00 |
| Meta | Muse Spark 1.1 | 1.00 |
| Alibaba | qwen3.8 | 1.50 |
| Zhipu AI (Z.AI) | glm-5.3 | 2.00 |

Rol netleştirmesi: Tablodaki her satır oy veren bir ajanı
temsil eder. Asistan satırı hem agregasyon hem oy hakkı içerir:
kendi oyunu §1.1 bias-free gereği dış ajanlardan bağımsız,
kendi kanıtıyla verir; agregasyon aşamasında kendi oyunu
toplam ağırlığa dahil eder; azınlık kaydında belirtir.

## 3. KARAR EŞİĞİ
- Ağırlıklı toplam = Σ(tüm oy veren ajanların ağırlıkları),
  asistan dahil.
- Oybirliği (tüm ağırlıklar aynı): kilitlenir.
- Ezici çoğunluk (≥%75 ağırlık): kilitlenir; azınlık DURUM'a.
- Split (<%75): asistan tie-break gerekçeli; PO nihai karar verir.
- Beraberlik (tam 50/50): PO nihai karar.
- ADVERSARIAL APPEAL: Tek ajan azınlıkta kalırsa ve yeni
  sandbox kanıtı sunarsa, çoğunluk yeniden değerlendirilir.
  Emsal: B3.5-AG (Round 4 A → Round 5 GLM appeal ile B).

## 4. KAÇIŞ (PO override)
4.1 PO her zaman nihai karar verir; ağırlıklı oy tavsiyedir.
4.2 PO ağırlık tablosunu değiştirebilir.
4.3 PO SORU setini değiştirebilir.
4.4 PO ajan ekleyip çıkarabilir.

## 5. ANTI-PATTERN (YASAK)
5.1 Prompt'a asistan önerisi/cevabı gömme (bias).
5.2 agent_identity yokluğu → geçersiz.
5.3 evidence_type yokluğu → geçersiz.
5.4 4-backtick wrapper yokluğu → geçersiz.
5.5 Sessiz ağırlık değişikliği → yasak.
5.6 Aynı ajana aynı soru iki kez sorma (round içinde).
5.7 Ajan cevabını yeniden yazma/tıraşlama → sentezde ham korunur.
5.8 Azınlık görüşünü yalnız oybirliği gerekçesiyle reddetmek
    → yasak (AG emsali).
5.9 Asistanın kendi oyunu agregasyona katmaması → yasak
    (§2 rol netleştirmesi).

## 6. DOSYA KONUMLARI
STORM-PROTOKOL.md — bu dosya (sabit; evrensel).
DURUM.md — round sonuçları.
PROTOKOL.md §0.7 — tek-satır atıf.