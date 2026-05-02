import io, re, uuid
from pathlib import Path

import pypdf
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import get_settings
from app.models.model import AllowedFileTypes, DocumentChunking

settings = get_settings()


def _extract_text_via_vision(page: pypdf.PageObject) -> str:
    """
    Fallback method that uses Tesseract OCR to extract text from a scanned PDF page.
    Converts the PDF page to an image and runs optical character recognition.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        writer = pypdf.PdfWriter()
        writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        images = convert_from_bytes(buf.read(), dpi=250)
        return "\n".join(pytesseract.image_to_string(img, lang="eng") for img in images).strip()
    except Exception:
        return ""


class DocumentProcessor:
    _SPLITTER = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    @staticmethod
    def verify_allowed_format(filename: str) -> AllowedFileTypes:
        """
        Ensures the provided file extension is permitted by the system.
        Raises ValueError if the extension is not supported.
        """
        ext = Path(filename).suffix.lstrip(".").lower()
        try:
            return AllowedFileTypes(ext)
        except ValueError:
            raise ValueError(f"Unsupported type '.{ext}'. Allowed: {[e.value for e in AllowedFileType]}")

    def ingest_plaintext_file(self, file_bytes: bytes, filename: str) -> tuple[str, list[DocumentChunking]]:
        """
        Processes a raw text file by decoding its bytes and chunking the resulting string.
        Returns the unique document ID and a list of chunks.
        """
        text = self._resolve_text_encoding(file_bytes, filename)
        doc_id = str(uuid.uuid4())
        return doc_id, self._split_into_segments(text, doc_id, filename)

    def yield_pdf_page_content(self, file_bytes: bytes, filename: str):
        """
        Iterates over pages in a PDF file, extracting text either natively or via OCR.
        Yields chunked data and metadata on a page-by-page basis to support streaming processing.
        """
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        total_pages = len(reader.pages)
        doc_id = str(uuid.uuid4())
        offset = 0
        for page_num, page in enumerate(reader.pages, start=1):
            used_ocr = False
            text = self._parse_pdf_natively(page)
            if not text:
                used_ocr = True
                text = _extract_text_via_vision(page)
            chunks = []
            if text:
                prefixed = f"[Page {page_num}/{total_pages}]\n{text}"
                chunks = self._split_into_segments(prefixed, doc_id, filename, page_num=page_num, offset=offset)
                offset += len(chunks)
            yield {"page_num": page_num, "total_pages": total_pages,
                   "doc_id": doc_id, "chunks": chunks,
                   "used_ocr": used_ocr, "text_found": bool(text)}

    @staticmethod
    def _parse_pdf_natively(page: pypdf.PageObject) -> str:
        """
        Attempts to read standard embedded text from a PDF without OCR.
        Strips control characters and normalizes whitespace.
        """
        for mode in ("layout", None):
            try:
                kwargs = {"extraction_mode": mode} if mode else {}
                raw = page.extract_text(**kwargs) or ""
                if raw.strip():
                    raw = re.sub(r"\n{3,}", "\n\n", raw)
                    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw)
                    return raw.strip()
            except Exception:
                continue
        return ""

    @staticmethod
    def _resolve_text_encoding(file_bytes: bytes, filename: str) -> str:
        """
        Tries multiple encodings to safely convert raw bytes into a python string.
        """
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return file_bytes.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        raise ValueError(f"Cannot decode '{filename}'.")

    def _split_into_segments(self, text, doc_id, filename, page_num=None, offset=0):
        """
        Uses langchain's recursive character text splitter to divide large text blocks
        into smaller sized chunks suitable for vector embedding and retrieval.
        """
        result = []
        for i, content in enumerate(self._SPLITTER.split_text(text)):
            meta = {"document_id": doc_id, "filename": filename, "chunk_index": offset + i}
            if page_num is not None:
                meta["page_number"] = page_num
            result.append(DocumentChunking(
                chunk_id=f"{doc_id}_{offset+i}", document_id=doc_id,
                content=content, metadata=meta,
            ))
        return result
