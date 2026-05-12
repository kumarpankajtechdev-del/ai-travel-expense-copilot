# Architecture

## Design Goals

- Keep AI workflow steps explicit and easy to test.
- Separate API models, orchestration, policy retrieval, and business rules.
- Make the local demo runnable without paid LLM or OCR dependencies.
- Provide clear extension points for production AI, OCR, and cloud services.

## Workflow

The claim review graph has four stages:

1. Parse receipt text into structured evidence.
2. Retrieve matching policy chunks from local policy documents.
3. Evaluate deterministic policy rules for explainable output.
4. Return a decision, risk score, reasons, references, and next action.

## Extension Points

| Component | Current implementation | Production upgrade |
|---|---|---|
| Receipt parsing | Regex parser | OCR + vision-language model |
| Policy retrieval | Token overlap retriever | Embeddings + vector database |
| Agent graph | Deterministic Python graph | LangGraph with checkpointing |
| Analytics | SQL schema | ClickHouse ingestion pipeline |
| Deployment | Docker Compose | AWS Lambda, Step Functions, SQS, SNS |

## Why a graph-based design?

A graph-based design makes AI systems easier to debug because each node has a clear input, output, and responsibility. It also maps well to production workflow engines such as Step Functions or LangGraph persistence.
