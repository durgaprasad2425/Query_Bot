# 🤖 Query Bot: Agentic RAG Chatbot

Query Bot is a high-performance, real-time AI assistant built with **FastAPI**, **LangChain**, and **OpenAI**. It specializes in **Retrieval-Augmented Generation (RAG)**, allowing users to upload documents and query them using an agentic workflow that can also browse the web and perform calculations.

![Query Bot Status](https://img.shields.io/badge/Status-Active-brightgreen)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat&logo=langchain)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat&logo=openai)

---

## 🌟 Key Features

### 🔍 Advanced Retrieval System
- **Hybrid Search**: Combines semantic vector search (**ChromaDB**) with traditional keyword search (**BM25**) using a reciprocal rank fusion approach.
- **Dynamic Context Injection**: Automatically injects relevant document snippets into the LLM's prompt based on the user's query.

### 📄 Sophisticated Ingestion
- **OCR Integration**: Uses **Tesseract OCR** and **pdf2image** to extract text from scanned PDFs that lack a text layer.
- **Smart Chunking**: Implements `RecursiveCharacterTextSplitter` with configurable chunk sizes and overlaps for optimal context preservation.
- **Multilingual Support**: Supports multiple text encodings (UTF-8, Latin-1, etc.) for robust document parsing.

### 🛠️ Agentic Capabilities
- **Autonomous Reasoning**: The agent (powered by GPT-4o) evaluates whether the document context is sufficient or if it needs to use external tools.
- **Web Search**: Integrated via Serper API for real-time information retrieval.
- **Calculator**: A precise tool for handling mathematical queries that LLMs might struggle with.

### ⚡ Real-time Experience
- **WebSocket Communication**: Tokens are streamed to the frontend as they are generated, providing a "typing" effect.
- **Progress Tracking**: Real-time progress bars for document uploads and indexing.

---

## 🏗️ Technical Architecture

### Backend Stack
- **Web Framework**: FastAPI (Asynchronous)
- **Orchestration**: LangChain (Expression Language)
- **Vector Store**: ChromaDB (On-disk persistence)
- **LLM**: OpenAI GPT-4o / GPT-4o-mini
- **Embeddings**: OpenAI `text-embedding-3-small`

### Why I am using
1. Backend Framework — FastAPI

Role: Core API layer and async runtime

Why this choice:
FastAPI provides an asynchronous execution model, which is essential for handling:

LLM streaming responses
concurrent embedding generation
external API calls (search, scraping)

Its tight integration with Pydantic ensures:

automatic request validation
type safety
predictable API behavior

2. Communication Layer — WebSocket (Single Persistent Channel)

Role: Real-time interaction between client and server

Why this design:
Instead of traditional HTTP request-response, the system uses a persistent WebSocket connection to support:

token-level streaming from the LLM
real-time document upload progress
bidirectional communication
session continuity without reconnects

Session context is maintained via session_id passed inside messages, enabling seamless switching without reopening connections.

3. LLM — OpenAI GPT-4o

Role: Core reasoning and response generation engine

Why this choice:

Strong function/tool-calling capability
Reliable instruction following
Handles multi-step reasoning (RAG + tools)

The model dynamically decides whether to:

answer directly
retrieve document context
call external tools (e.g., web search)

This removes the need for rigid rule-based routing.

4. Agent Orchestration — LangGraph

Role: Controls reasoning flow and tool execution

Why this choice:
LangGraph models the system as an explicit state machine:

User Input → Retrieval → LLM → Tool → LLM → Response

Advantages:

transparent execution flow
easier debugging
modular node-based design
simple extension (add validator, router, memory nodes)
5. Vector Store — ChromaDB

Role: Stores and retrieves document embeddings

Why this choice:

Embedded database (no external infrastructure)
persistent local storage
efficient similarity search

The abstraction layer allows seamless migration to managed solutions like Pinecone or Weaviate if needed.

6. Embeddings — OpenAI text-embedding-3-small

Role: Converts text into semantic vectors

Why this choice:

strong semantic understanding
cost-efficient for large-scale usage
suitable for document chunk retrieval

Used for dense retrieval to capture contextual similarity beyond exact keyword matches.

7. Hybrid Retrieval — BM25 + Vector Search

Role: Improves retrieval accuracy

Why this design:

The system combines:

Dense retrieval (embeddings): captures semantic meaning
Sparse retrieval (BM25): captures exact matches

This hybrid approach ensures:

better recall for technical terms, IDs, and keywords
improved overall relevance
8. Web Search — Serper API

Role: Provides real-time external knowledge

Why this choice:

returns structured Google results
supports answer boxes and knowledge panels
enables retrieval of full page content

Used only when:

information is time-sensitive
confidence in internal knowledge is low
9. Document Processing — PDF Pipeline

Components:

pypdf
pdf2image
pytesseract

Why this design:

Two-stage extraction strategy:

Native text extraction (fast, accurate for digital PDFs)
OCR fallback (for scanned/image-based documents)

This ensures robust handling across different document types.

🧠 System-Level Design Summary

The system follows a hybrid agentic RAG architecture:

User Query
   ↓
Intent Handling
   ↓
Hybrid Retrieval (BM25 + Vector DB)
   ↓
LLM Reasoning (GPT-4o)
   ↓
Tool Usage (Web Search / Calculator)
   ↓
Streaming Response via WebSocket

### Project Structure
```text
Query_Bot/
├── app/
│   ├── agents/           # RAGAgent and Tool binding logic
│   ├── api/              # WebSocket handlers and event dispatchers
│   ├── core/             # Configuration, dependencies, and session management
│   ├── knowledge_base/   # Document processing, VectorStore, and HybridRetriever
│   ├── models/           # Pydantic schemas for API and internal data
│   ├── tools/            # WebSearch and Calculator implementations
│   └── validators/       # AI-driven response quality assessment
├── frontend/             # Premium Glassmorphism UI (Static Files)
├── chroma_db/            # Persistent storage for embeddings
├── sessions/             # Local history for chat persistence
└── main.py               # Application entry point
```

---

## ⚙️ Configuration (.env)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | Your OpenAI API Key (**Required**) | - |
| `OPENAI_MODEL` | The LLM model to use | `gpt-4o` |
| `SERPER_API_KEY` | Key for web search tool (Optional) | `""` |
| `CHUNK_SIZE` | Size of document chunks | `700` |
| `CHUNK_OVERLAP` | Overlap between chunks | `100` |
| `RETRIEVAL_TOP_K` | Number of chunks to retrieve | `5` |

---

## 🔌 WebSocket Protocol

Query Bot communicates via a single WebSocket endpoint at `/ws/main`.

### Client to Server Messages
```json
{ "type": "chat", "message": "What is in the document?", "session_id": "uuid" }
{ "type": "upload", "filename": "data.pdf", "data": "base64_string" }
{ "type": "sessions_list" }
{ "type": "session_load", "session_id": "uuid" }
```

### Server to Client Events
- `chat_token`: Individual tokens for streaming.
- `chat_done`: Signals the end of a response with a quality verdict.
- `upload_start/page_done/upload_complete`: Progress updates for ingestion.
- `search_web/use_calculator`: Notifies the UI that the agent is using a tool.

---

## 📥 Installation & Setup

### 1. Prerequisites
- Python 3.10+
- **Tesseract OCR**: Required for scanned PDF support.
  - *Windows*: [Download Installer](https://github.com/UB-Mannheim/tesseract/wiki)
  - *Linux*: `sudo apt install tesseract-ocr`

### 2. Environment Setup
```bash
# Clone and enter directory
git clone https://github.com/your-repo/Query_Bot.git
cd Query_Bot

# Create and activate venv
python -m venv venv
source venv/bin/activate  # Or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Start the Server
```bash
python main.py
```
Open `http://localhost:8080` in your browser.

---

## 📐 System Architecture

### High-Level Architecture
Query Bot follows a modern asynchronous architecture with a decoupled frontend and an agent-driven backend.

```mermaid
graph TD
    User((User)) <--> |WebSocket| API[FastAPI WebSocket]
    API <--> |JSON Events| Manager[Session Manager]
    Manager <--> |Retrieve/Store| Sessions[(Local Sessions)]
    
    subgraph "Ingestion Pipeline"
        API --> |Raw Bytes| Processor[Document Processor]
        Processor --> |Native/OCR| Text[Text Extraction]
        Text --> |Chunking| Chunker[Text Splitter]
        Chunker --> |Embeddings| VectorStore[(ChromaDB)]
        Chunker --> |Keywords| BM25[BM25 Index]
    end
    
    subgraph "Reasoning Loop"
        API <--> |Query| Agent[RAG Agent]
        Agent <--> |Hybrid Search| Retriever[Retriever]
        Retriever --> VectorStore
        Retriever --> BM25
        Agent <--> |Function Call| Tools[Tools: Web/Math]
        Agent --> |Completion| LLM[OpenAI GPT-4o]
    end
```

### 🔄 Data Flow (Input ➔ Output)

#### 1. Ingestion Flow
1. **Input**: User uploads a file (PDF/TXT) via the UI.
2. **Transfer**: File is sent as a Base64 string over WebSocket.
3. **Processing**: 
   - `pypdf` extracts text natively.
   - If empty, **Tesseract OCR** processes the image layer.
4. **Storage**: Text is split into 700-character chunks. ChromaDB stores vector embeddings, while a local BM25 index is built for keyword parity.
5. **Output**: Success event sent to UI, document is now "searchable".

#### 2. Query Flow
1. **Input**: User sends a natural language question.
2. **Context**: The `HybridRetriever` pulls the top-K most relevant chunks using both Vector and BM25 scores.
3. **Reasoning**: The LLM analyzes the chunks. If it needs more data, it calls the `WebSearchTool`.
4. **Streaming**: As the LLM generates the answer, tokens are dispatched immediately via WebSocket.
5. **Validation**: The `ResponseValidator` checks the final output for hallucinations or low confidence.
6. **Output**: Final tokens + confidence verdict displayed to the user.

---

## 🎯 Use Cases

- **📄 Research Assistant**: Upload dense academic papers and ask for summaries or specific methodology details..
- **🛠️ Technical Support**: Feed product manuals into the bot to create an instant searchable help desk for customers.
- **🕵️ Data Fact-Checking**: Use the Agent's web search capability to verify claims found within uploaded internal documents.

---

## ❓ Troubleshooting

**`ModuleNotFoundError: No module named 'langchain_core'`**
> Ensure you have installed all requirements: `pip install -r requirements.txt`. If issues persist, run `pip install langchain-core langchain-openai`.

**`ModuleNotFoundError: No module named 'pydantic_settings'`**
> Run `pip install pydantic-settings` to fix missing environment configuration dependencies.

**OCR not working for PDFs**
> Ensure `tesseract` is in your system PATH. On Windows, you may need to specify the path in `app/knowledge_base/ingestion.py` or ensure the installer added it to the environment variables.

**Vector DB Connection Errors**
> Delete the `chroma_db/` folder and restart the application to re-initialize the database.

---
