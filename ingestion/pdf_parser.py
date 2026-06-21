from pypdf import PdfReader
import os

class PdfParser:
    def __init__(self, vector_store):
        self.store = vector_store

    def ingest_pdf(self, file_path: str) -> int:
        """
        Parses a PDF file and adds its pages to the vector store.
        Returns the number of pages successfully ingested.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
            
        if not file_path.lower().endswith('.pdf'):
            raise ValueError("File must be a PDF document.")
            
        try:
            reader = PdfReader(file_path)
            file_name = os.path.basename(file_path)
            pages_ingested = 0
            
            # Read the PDF page by page
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                
                # Only save pages that actually have extractable text
                if text and text.strip():
                    clean_text = f"Source PDF: {file_name} (Page {i+1})\n\n{text.strip()}"
                    
                    self.store.add_memory(
                        text=clean_text,
                        source=f"pdf:{file_name}"
                    )
                    pages_ingested += 1
                    
            if pages_ingested == 0:
                raise ValueError("No extractable text found in the PDF. It may be an image-based scan.")
                
            return pages_ingested
            
        except Exception as e:
            raise Exception(f"Failed to parse PDF: {str(e)}")
