# Architecture
React frontend -> FastAPI REST API -> trace validation/normalization -> failure detection -> diagnosis
-> correction approval -> controlled task runner/replay -> evaluation -> SQLite/JSON storage.
Detectors are deterministic and independent; an LLM is optional and only used for wording.
