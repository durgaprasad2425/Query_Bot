import asyncio
import base64
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.dependencies import init_rag_agent, init_document_retriever, init_response_validator, init_vector_database
from app.core.sessions import (
    register_interaction, purge_thread_data, pull_message_timeline, query_all_active_threads,
)
from app.core.web_socket import ws_manager
from app.models.model import AllowedFileTypes
from app.knowledge_base.ingestion import DocumentProcessor

router = APIRouter()
_pool  = ThreadPoolExecutor(max_workers=4)


@router.websocket("/ws/main")
async def ws_handler(ws: WebSocket):
    """
    Single persistent connection per browser tab.
    session_id is read from each message body — no reconnect needed on session switch.
    """
    conn_id = str(__import__('uuid').uuid4())
    await ws_manager.register_client(conn_id, ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.transmit_event(conn_id, "error", {"detail": "Invalid JSON"})
                continue

            t = msg.get("type")
            session_id = msg.get("session_id", conn_id)

            if t == "ping":
                await ws_manager.transmit_event(conn_id, "pong", {})

            elif t == "status":
                vs = init_vector_database()
                await ws_manager.transmit_event(conn_id, "status", {"total_chunks": vs.record_count})

            elif t == "sessions_list":
                await ws_manager.transmit_event(conn_id, "sessions_list", {"sessions": query_all_active_threads()})

            elif t == "session_load":
                sid  = msg.get("session_id", "")
                msgs = pull_message_timeline(sid)
                await ws_manager.transmit_event(conn_id, "session_history", {
                    "session_id": sid, "messages": msgs
                })

            elif t == "session_delete":
                sid = msg.get("session_id", "")
                purge_thread_data(sid)
                await ws_manager.transmit_event(conn_id, "session_deleted", {"session_id": sid})

            elif t == "upload":
                asyncio.create_task(
                    _handle_upload(conn_id, session_id, msg.get("filename", ""), msg.get("data", ""))
                )

            elif t == "chat":
                asyncio.create_task(
                    _handle_chat(conn_id, session_id, msg.get("message", ""))
                )

            else:
                await ws_manager.transmit_event(conn_id, "error", {"detail": f"Unknown type: {t}"})

    except WebSocketDisconnect:
        ws_manager.unregister_client(conn_id, ws)
    except Exception:
        ws_manager.unregister_client(conn_id, ws)

async def _handle_upload(conn_id: str, session_id: str, filename: str, b64_data: str) -> None:
    send = lambda ev, d: ws_manager.transmit_event(conn_id, ev, d)

    # Validate inputs
    if not filename:
        await send("upload_error", {"detail": "No filename provided."}); return

    try:
        file_type = DocumentProcessor.verify_allowed_format(filename)
    except ValueError as e:
        await send("upload_error", {"detail": str(e)}); return

    try:
        file_bytes = base64.b64decode(b64_data)
    except Exception:
        await send("upload_error", {"detail": "Invalid file data."}); return

    if len(file_bytes) > 20 * 1024 * 1024:
        await send("upload_error", {"detail": "File exceeds 20 MB limit."}); return

    vs        = init_vector_database()
    retriever = init_document_retriever()
    processor = DocumentProcessor()
    all_chunks = []
    doc_id     = None

    try:
        if file_type == AllowedFileTypes.TXT:
            await send("upload_start", {
                "filename": filename, "total_pages": 1,
                "has_ocr": False, "message": "Parsing text file…"
            })
            doc_id, chunks = await asyncio.get_event_loop().run_in_executor(
                _pool, processor.ingest_plaintext_file, file_bytes, filename
            )
            if chunks:
                vs.insert_documents(chunks)
                all_chunks = chunks
            await send("page_done", {
                "page": 1, "total_pages": 1, "chunks": len(chunks),
                "used_ocr": False, "pct": 100,
            })

        else:
            import pypdf
            import io as _io
            reader      = pypdf.PdfReader(_io.BytesIO(file_bytes))
            total_pages = len(reader.pages)
            first_text  = processor._parse_pdf_natively(reader.pages[0]) if total_pages else ""
            has_ocr     = not bool(first_text)

            await send("upload_start", {
                "filename": filename,
                "total_pages": total_pages,
                "has_ocr": has_ocr,
                "message": (
                    "Scanned PDF detected — OCR will extract text. This may take a moment."
                    if has_ocr else f"Processing {total_pages} page(s)…"
                ),
            })

            def _process_pages():
                return list(processor.yield_pdf_page_content(file_bytes, filename))

            page_results = await asyncio.get_event_loop().run_in_executor(_pool, _process_pages)

            for pr in page_results:
                doc_id = pr["doc_id"]
                if pr["chunks"]:
                    vs.insert_documents(pr["chunks"])
                    all_chunks.extend(pr["chunks"])

                pct = int(pr["page_num"] / pr["total_pages"] * 100)
                await send("page_done", {
                    "page":       pr["page_num"],
                    "total_pages": pr["total_pages"],
                    "chunks":     len(pr["chunks"]),
                    "used_ocr":   pr["used_ocr"],
                    "text_found": pr["text_found"],
                    "pct":        pct,
                })
                await asyncio.sleep(0)  

            if not all_chunks:
                await send("upload_error", {
                    "detail": (
                        "No text could be extracted from this PDF.\n"
                       
                    )
                })
                return

        retriever.recalculate_bm25_index()

        await send("upload_complete", {
            "filename":     filename,
            "total_chunks": len(all_chunks),
            "doc_id":       doc_id,
        })

    except Exception as e:
        await send("upload_error", {"detail": str(e)})


# Chat handling
async def _handle_chat(conn_id: str, session_id: str, message: str) -> None:
    if not message.strip():
        return

    agent     = init_rag_agent()
    validator = init_response_validator()

    register_interaction(session_id, "user", message)

    collected: list[str] = []

    async def on_tool_use(event_name: str, data: dict):
        await ws_manager.transmit_event(conn_id, event_name, data)

    try:
        async for token in agent.generate_answer_stream(
            session_id=session_id,
            user_message=message,
            on_tool_use=on_tool_use,
        ):
            await ws_manager.transmit_event(conn_id, "chat_token", {"token": token})
            collected.append(token)

        full_response = "".join(collected)

        register_interaction(session_id, "assistant", full_response)

        try:
            validation = await validator.assess_response_quality(message, full_response)
        except Exception:
            validation = {"confidence": "medium", "verdict": ""}

        await ws_manager.transmit_event(conn_id, "chat_done", {
            "confidence": validation.get("confidence", "medium"),
            "verdict":    validation.get("verdict", ""),
        })

        await ws_manager.transmit_event(conn_id, "sessions_list", {"sessions": query_all_active_threads()})

    except Exception as e:
        await ws_manager.transmit_event(conn_id, "chat_error", {"detail": str(e)})