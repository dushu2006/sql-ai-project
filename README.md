# 🚀 AI SQL Agent – Intelligent Database Assistant

An AI-powered system that transforms natural language into accurate SQL queries with context-aware understanding, intelligent error handling, and structured data responses. Designed to simplify database interaction for both technical and non-technical users.

## 🧠 Overview
This project enables users to query databases using plain English instead of writing complex SQL. It leverages a locally running Large Language Model via Ollama to interpret user intent, generate optimized SQL queries, and return meaningful results through a clean dashboard interface.

## ✨ Features
- Natural Language → SQL conversion
- Context-aware understanding (e.g., "staff" → "workers")
- Two-step response generation (interpretation + execution)
- AI-powered query correction and validation
- Interactive dashboard for structured results
- Handles complex joins (customers, workers, sales, products)
- Robust error handling (422 errors, schema mismatches, fetch issues)
- Local AI execution for privacy and performance

## 🤖 AI & Model Integration
- Powered by **Ollama** for running LLMs locally
- Uses models like **LLaMA 3 / Mistral** (configurable)
- Two-stage pipeline:
  1. **Query Understanding Layer** – Converts natural language into structured intent
  2. **SQL Generation Layer** – Produces optimized SQL queries based on schema
- Reduces hallucinations by grounding responses in database schema

## 🛠️ Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** HTML, CSS, JavaScript (Dashboard UI)
- **Database:** SQLite / MySQL
- **AI Engine:** Ollama (Local LLM serving)

## ⚙️ Run Locally

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
