import asyncio
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

# Import the actual RAG logic from your app
from app.core.dependencies import init_rag_agent, init_vector_database, init_document_retriever
from app.core.sessions import register_interaction
from app.knowledge_base.ingestion import DocumentProcessor

app = FastAPI(title="Real-time Query Bot API")

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.get("/")
async def root():
    return {"message": "API is online. POST to /chat for raw text streaming."}

@app.post("/chat")
async def chat_streaming(request: ChatRequest):
    """
    Streams the AI response as raw text tokens (String format).
    """
    agent = init_rag_agent()
    
    # Register the user's message
    register_interaction(request.session_id, "user", request.message)

    async def token_generator():
        collected_tokens = []
        try:
            async for token in agent.generate_answer_stream(
                session_id=request.session_id,
                user_message=request.message
            ):
                # Send the raw string chunk
                yield token
                collected_tokens.append(token)
            
            # Save the full answer once streaming is done
            full_response = "".join(collected_tokens)
            register_interaction(request.session_id, "assistant", full_response)
            
        except Exception as e:
            yield f"\n[STREAM_ERROR: {str(e)}]"

    # Using text/plain so it behaves like a raw string stream
    return StreamingResponse(token_generator(), media_type="text/plain")

@app.post("/upload")
async def upload_file(
    session_id: str = Form(...), 
    file: UploadFile = File(...)
):
    """
    Standard multipart file upload.
    """
    processor = DocumentProcessor()
    vs = init_vector_database()
    retriever = init_document_retriever()
    
    try:
        file_bytes = await file.read()
        filename = file.filename
        
        if filename.endswith('.txt'):
            doc_id, chunks = await asyncio.get_event_loop().run_in_executor(
                None, processor.ingest_plaintext_file, file_bytes, filename
            )
            if chunks: vs.insert_documents(chunks)
        else:
            def _process_pdf():
                return list(processor.yield_pdf_page_content(file_bytes, filename))
            
            page_results = await asyncio.get_event_loop().run_in_executor(None, _process_pdf)
            for pr in page_results:
                if pr["chunks"]:
                    vs.insert_documents(pr["chunks"])
        
        retriever.recalculate_bm25_index()
        return {"status": "success", "filename": filename, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
