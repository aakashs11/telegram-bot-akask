##
## Roadmap for ASK.ai Telegram Tutor

### Delivered now (working bot)
- Stable multi-turn with OpenAI Responses API:
  - Correct content types: system/user → input_text; assistant → output_text
  - Retry with minimal context on 400s
  - Graceful fallback and logging
- Slot-filling for notes/videos with pending state
- Safer screening (greeting allowlist + robust parsing)
- Portable notes index path + Cloud Run-ready config

### High-priority next (1–2 days)
- Improve slot extraction with a tiny extractor call (regex + 1-shot LLM)
- “Summarize URL” tool for YouTube links (captions or model summary)
- Image handling in Telegram (OCR or VLM) for homework help
- Add simple unit tests for formatting, screening, routing
- Observability: log action, slots, latency, tokens, request_id

### Medium term (3–7 days)
- Vector search over local docs (faiss/chromadb) behind `retrieve(query)` tool
- Evaluation harness and dataset (slot-fill success, routing accuracy, response length compliance)
- A/B environment variables for model selection and parameters
- Cloud Run dev/prod triggers and blue/green rollouts with min instances

### Later
- Rich tutoring flows with step-by-step solutions and references
- RAG on large content sets with ingestion pipeline
- Admin tooling to update `data/index.json` and validate links
- Rate limiting and caching for YouTube/Sheets

### Notes
- Keep the controller simple: Safety → Router → Slot fill → Tool → Compose
- Avoid recursive agent loops; at most 2 LLM calls per user turn for UX

