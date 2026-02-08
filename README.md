# CoeusAI — Voice-based Context-Aware Assistant (RAG)

CoeusAI is a voice-driven assistant that understands user context and answers questions using **Retrieval-Augmented Generation (RAG)**.  
It combines speech input → transcription → retrieval from a knowledge base → LLM response → (optional) speech output.

## Features
- 🎙️ Voice-first interaction (STT input, optional TTS output)
- 🧠 Context-aware conversations (session memory / chat history)
- 📚 RAG pipeline for grounded answers from your documents
- ⚡ FastAPI backend with `/` and `/health` endpoints
- ✅ Test suite with pytest

## High-level Architecture
1. **Audio input** (client)
2. **Speech-to-Text (STT)** → transcript
3. **Retriever** (vector DB / embeddings) → relevant chunks
4. **LLM** → answer grounded in retrieved context
5. **Text-to-Speech (TTS)** (optional) → audio output

## Project Structure (example)