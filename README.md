# AI Incident Response Agent

Paste an error log, get a full incident report in about 11 seconds.

Five agents run in sequence: one classifies the error, one finds the exact file and line, one searches past incidents for similar failures, one suggests fixes based on how those past incidents were resolved, and one writes the report. You watch each agent finish in real time.

**Live demo:** https://ai-incident-response-agent-1.onrender.com

Click Investigate, then "Try Sample Log."

---

## The agents

1. **Error Analyzer** — error type and affected service from Gemini, severity from a trained scikit-learn model
2. **Root Cause Investigator** — parses the stack trace for file, line, function, and explains why it failed
3. **Historical Pattern Search** — semantic search over past incidents using ChromaDB and Google embeddings
4. **Fix Suggester** — generates specific code fixes, grounded in how similar incidents were actually resolved
5. **Report Writer** — compiles everything into a structured markdown report

Agents don't call each other. They read and write a shared state object, which is what lets any one of them fail without killing the pipeline.

---

## Results

Tested on 15 error logs across 5 error types against a 24-incident corpus.

**Retrieval (Agent 3)**
- Recall@1: 15/15
- Recall@3: 15/15
- MRR: 1.000
- Mean latency: 643 ms

Also tested with no metadata at all (raw log text only) — same results, which means the embeddings alone are matching "shipping address is null" to "billing contact null dereference." Garbage input correctly returns zero matches instead of confidently citing something unrelated.

**Severity classifier**
- 80% accuracy, 5-fold cross-validation
- 99 samples, 17 features
- Random Forest

**Pipeline**
- ~11 seconds end-to-end
- 4 Gemini calls + 1 embedding query per investigation

---

## Stack

LangGraph, LangChain, ChromaDB, Google Gemini, scikit-learn, FastAPI, SQLite, plain HTML/CSS/JS.

No Node.js, no build step. The frontend is static files served by FastAPI.

---

## Structure

agents/ 5 agent nodes + shared state + graph wiring
rag/ chunking, vector store, two-stage retriever
models/ severity classifier (train + predict)
api/ FastAPI endpoints + static frontend
database.py sqlite3, no ORM
data/ 15 test logs, 24 seed incidents, ground truth
evaluation/ benchmark results
