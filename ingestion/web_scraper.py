import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse

class WebScraper:
    def __init__(self, vector_store):
        self.store = vector_store
        # Headers to masquerade as a normal browser to avoid simple bot blocks
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def is_valid_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def ingest_url(self, url: str) -> bool:
        """Scrapes an article from a URL and adds it to the vector store."""
        if not self.is_valid_url(url):
            raise ValueError("Invalid URL format.")

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()

            # Get the page title
            title = soup.title.string if soup.title else "Untitled Page"
            
            # Get text and clean it up
            text = soup.get_text(separator=' ')
            
            # Collapse multiple spaces and newlines
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            if not clean_text:
                raise ValueError("Could not extract any meaningful text from the page.")
                
            # Prepend title for context
            final_text = f"Title: {title.strip()}\nURL: {url}\n\n{clean_text}"
            
            # We add it as a single chunk for now (Chroma/Embedding model handles length)
            # In a production system, we'd chunk this intelligently by paragraphs
            self.store.add_memory(
                text=final_text[:8000], # Hard cap to prevent blowing up the embedding context
                source=f"url:{url}"
            )
            return True
            
        except Exception as e:
            raise Exception(f"Failed to scrape URL: {str(e)}")
