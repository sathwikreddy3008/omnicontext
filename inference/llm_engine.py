import ollama
from core.config import OLLAMA_MODEL

SYSTEM_PROMPT = """You are my 'Second Brain' AI assistant. 
You answer my questions based ONLY on the context provided below, which comes from my digital history (clipboard, code, etc).
If the context doesn't contain the answer, say 'I don't have a memory of that.' Don't make things up.

CONTEXT:
{context}
"""

class BrainEngine:
    def __init__(self):
        self.model_name = OLLAMA_MODEL
        self.conversation_history = []
        
    def clear_history(self):
        self.conversation_history = []

    def _build_messages(self, query: str, context: str) -> list:
        """Build the message array with system prompt, history, and new query."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": query})
        return messages

    def _save_to_history(self, query: str, answer: str):
        """Save exchange to short-term memory, keeping last 10 messages."""
        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append({"role": "assistant", "content": answer})
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

    def ask(self, query: str, context: str) -> str:
        """Asks the local LLM a question (blocking, returns full answer)."""
        try:
            messages = self._build_messages(query, context)
            response = ollama.chat(model=self.model_name, messages=messages)
            answer = response['message']['content']
            self._save_to_history(query, answer)
            return answer
        except Exception as e:
            return f"Error connecting to local LLM: {str(e)}\n\nMake sure Ollama is installed and running (`ollama serve`)."

    def ask_stream(self, query: str, context: str):
        """Streams the LLM response token-by-token. Yields each text chunk."""
        try:
            messages = self._build_messages(query, context)
            full_answer = ""
            
            for chunk in ollama.chat(model=self.model_name, messages=messages, stream=True):
                token = chunk['message']['content']
                full_answer += token
                yield token
            
            # Save the completed answer to history
            self._save_to_history(query, full_answer)
            
        except Exception as e:
            yield f"Error connecting to local LLM: {str(e)}\n\nMake sure Ollama is installed and running (`ollama serve`)."

