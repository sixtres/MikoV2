# STORM PROTOCOL
File: STORM-PROTOKOL.md (SSOT)
Owner: PO (Eser Göbekli)
Purpose: Verify project decisions with multiple independent LLMs
         (bias-free, evidence-mandatory, traceable).

Application: PROTOKOL.md §1.7 references this protocol. This file
is self-contained; it carries content independent of PROTOKOL.md.

## 0. WHAT / WHY / HOW
What: Ask a QUESTION set to N independent agents, synthesize with weighted voting.
Why: Single-agent bias, blind spots, lack of traceability.
How: Stage 1 (prompt preparation) → Stage 2 (agents) → Stage 3
     (weighted synthesis) → Stage 4 (PO final decision).

## 1. BASIC PRINCIPLES
1.1 Bias-free: Assistant recommendation/answer is NOT given to agents.
    The assistant submits its own vote with §2 weight; the vote is based on
    independent evidence.
1.2 Evidence mandatory: evidence_type ∈ {sandbox_test, code_review,
    logical_reasoning, prior_experience, external_doc}.
    sandbox_test → setup + observation detail mandatory.
1.3 Identity mandatory: family + model + self_reported=true.
1.4 Format mandatory: answer in a single 4-backtick code block; first
    line inside the block is the marker `#json`; the remainder is the
    JSON payload conforming to the answer schema.
1.5 prompt_version + prompt_version_acknowledged mandatory.
1.6 Weight table is calibrated; PO changes it.
1.7 Transparency: every round result in DURUM.md; minority separately.
1.8 Sandbox-diversity annotation: when a question is sandbox-testable
    (the answer can be produced by running code locally), an agent
    returning only code_review or logical_reasoning evidence is
    annotated in the synthesis as evidence-diversity-incomplete. The
    answer remains valid; the annotation is a calibration signal.

## 2. WEIGHT TABLE
| Agent (family) | Model | Weight |
|---|---|---|
| Anthropic (assistant) | claude-sonnet-4.5 | 1.25 |
| OpenAI | gpt-5 | 1.00 |
| Google | gemini-2.5-pro | 1.00 |
| Meta | Muse Spark 1.1 | 1.00 |
| Alibaba | qwen3.8 | 1.50 |
| Zhipu AI (Z.AI) | glm-5.3 | 2.00 |
| xAI | grok-4.5 | 1.00 |

Role clarification: Each row in the table represents an agent that
votes. The assistant row includes both aggregation and voting right:
it gives its own vote independently from external agents per §1.1
bias-free, with its own evidence; during aggregation it includes its own
vote in the total weight; it notes this in the minority record.

## 3. DECISION THRESHOLD
- Weighted total = Σ(weights of all voting agents),
  including the assistant.
- Unanimity (all weights same): locked.
- Overwhelming majority (≥75% weight): locked; minority to DURUM.
- Split (<75%): assistant tie-break with rationale; PO makes final decision.
- Tie (exact 50/50): PO final decision.
- ADVERSARIAL APPEAL: If a single agent remains in minority and presents
  new sandbox evidence, the majority is re-evaluated.
  Precedent: B3.5-AG (Round 4 A → Round 5 GLM appeal to B).

## 4. OVERRIDE (PO override)
4.1 PO always makes the final decision; weighted vote is advisory.
4.2 PO can change the weight table.
4.3 PO can change the QUESTION set.
4.4 PO can add/remove agents.

## 5. ANTI-PATTERN (FORBIDDEN)
5.1 Embedding assistant recommendation/answer in the prompt (bias).
5.2 Missing agent_identity → invalid.
5.3 Missing evidence_type → invalid.
5.4 Missing 4-backtick wrapper → invalid.
5.5 Silent weight change → forbidden.
5.6 Asking the same agent the same question twice (within a round).
5.7 Rewriting/trimming the agent answer → raw preserved in synthesis.
5.8 Rejecting the minority view solely on unanimity grounds
    → forbidden (AG precedent).
5.9 Assistant not including its own vote in aggregation → forbidden
    (§2 role clarification).

## 6. FILE LOCATIONS
STORM-PROTOKOL.md — this file (fixed; universal).
DURUM.md — round results.
PROTOKOL.md §1.7 — single-line reference.