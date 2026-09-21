"""
RAG generation pipeline with configurable LLM provider abstraction.
Supports: Gemini, other OpenAI-compatible providers, ollama, mock
Prompt includes retrieved context + source metadata + citation instruction.
If context insufficient -> "Insufficient information in the provided documents."
"""
import os
import time
from typing import List, Dict, Tuple, Optional
from .config import get_llm_config, GENERATION_SYSTEM_PROMPT
from .utils import logger

class LLMProvider:
    def __init__(self, config: Dict = None):
        self.config = config or get_llm_config()
        self.provider = self.config.get("provider","mock")
        self.model = self.config.get("model","gpt-4o-mini")
        self.temperature = self.config.get("temperature",0.1)
        self.max_tokens = self.config.get("max_tokens",512)
        self.client = None
        self._init_client()

    def _init_client(self):
        if self.provider in ["gemini", "openai", "groq", "openrouter", "together"]:
            try:
                from openai import OpenAI
                api_key = self.config.get("api_key") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
                base_url = self.config.get("base_url")
                # Groq and OpenRouter have different base URLs
                if self.provider == "gemini":
                    base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
                elif self.provider == "groq":
                    base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
                elif self.provider == "openrouter":
                    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
                
                if not api_key and self.provider != "mock":
                    logger.warning(f"No API key for provider {self.provider}, will use mock if generation attempted")
                    return
                
                self.client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
                logger.info(f"Initialized OpenAI-compatible client for {self.provider}, model {self.model}")
            except Exception as e:
                logger.error(f"Failed to init OpenAI client: {e}")
        elif self.provider == "ollama":
            # Ollama uses OpenAI-compatible endpoint or direct requests
            logger.info(f"Ollama provider configured at {self.config.get('ollama_url')}")
        elif self.provider == "mock":
            logger.info("Using mock LLM provider (no API calls)")

    def _build_prompt(self, question: str, retrieved_chunks: List[Dict]) -> Tuple[str, str]:
        """Build system and user prompt"""
        context_parts = []
        for chunk in retrieved_chunks:
            doc = chunk.get("document","Unknown")
            page = chunk.get("page","?")
            text = chunk.get("text","")
            context_parts.append(f"[{doc}, p. {page}]\n{text}\n")
        
        context_str = "\n---\n".join(context_parts) if context_parts else "No context retrieved."

        user_prompt = f"""Question: {question}

Retrieved Context:
{context_str}

Instructions:
- Answer ONLY using the retrieved context above.
- If context is insufficient, say "Insufficient information in the provided documents."
- Cite sources for every factual statement as [Document, p. X]
- Be concise and accurate.
- Do not invent citations.

Answer:"""
        return GENERATION_SYSTEM_PROMPT, user_prompt

    def generate(self, question: str, retrieved_chunks: List[Dict]) -> Tuple[str, float, Dict]:
        """
        Generate answer.
        Returns: (answer, generation_time_ms, metadata)
        """
        system_prompt, user_prompt = self._build_prompt(question, retrieved_chunks)
        
        start = time.perf_counter()

        # Mock mode
        if self.provider == "mock" or not self.client:
            # If Ollama, try simple request
            if self.provider == "ollama":
                try:
                    import requests
                    ollama_url = self.config.get("ollama_url","http://localhost:11434")
                    payload = {
                        "model": self.model,
                        "prompt": f"{system_prompt}\n\n{user_prompt}",
                        "stream": False,
                        "options": {"temperature": self.temperature, "num_predict": self.max_tokens}
                    }
                    resp = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=60)
                    if resp.status_code == 200:
                        ans = resp.json().get("response","")
                        gen_time = (time.perf_counter() - start)*1000
                        return ans, gen_time, {"provider": "ollama", "model": self.model}
                    else:
                        logger.warning(f"Ollama error {resp.status_code}: {resp.text}")
                except Exception as e:
                    logger.warning(f"Ollama generation failed: {e}, falling back to mock")

            # Mock logic: synthesize answer from retrieved chunks if possible
            if not retrieved_chunks:
                answer = "Insufficient information in the provided documents."
            else:
                # Simple extractive mock: take top chunk and summarize first 2 sentences + citations
                top = retrieved_chunks[0]
                # naive summary: first 150 words
                words = top["text"].split()[:120]
                snippet = " ".join(words)
                doc = top["document"]
                page = top["page"]
                answer = f"Based on retrieved documents: {snippet}... [{doc}, p. {page}]"
                # If multiple chunks, mention
                if len(retrieved_chunks) > 1:
                    answer += f" Additional context from {len(retrieved_chunks)-1} other chunks supports this."
            gen_time = (time.perf_counter() - start)*1000
            # Simulate some latency
            # time.sleep(0.1)
            return answer, gen_time, {"provider": "mock", "model": "mock-extractive", "note": "Configure LLM_PROVIDER and API key for real generation"}

        # Real OpenAI-compatible generation, including Gemini's compatible endpoint
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            answer = response.choices[0].message.content.strip()
            gen_time = (time.perf_counter() - start)*1000
            meta = {
                "provider": self.provider,
                "model": self.model,
                "usage": getattr(response, 'usage', None).__dict__ if hasattr(response, 'usage') else None,
            }
            return answer, gen_time, meta
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to mock
            fallback_answer = f"LLM generation failed ({e}). Retrieved context: {retrieved_chunks[0]['text'][:200] if retrieved_chunks else 'No context'}"
            gen_time = (time.perf_counter() - start)*1000
            return fallback_answer, gen_time, {"provider": self.provider, "error": str(e), "fallback": "mock"}

# Singleton
_llm_instance: Optional[LLMProvider] = None

def get_llm_provider() -> LLMProvider:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMProvider()
    return _llm_instance

def generate_answer(question: str, retrieved_chunks: List[Dict]) -> Tuple[str, float, Dict]:
    provider = get_llm_provider()
    return provider.generate(question, retrieved_chunks)

if __name__ == "__main__":
    # quick test
    test_chunks = [{"document":"Information_Brochure_2026.pdf","page":1,"text":"IIT Roorkee offers M.Tech programs requiring 60% marks for General category."}]
    ans, t, meta = generate_answer("What is eligibility for M.Tech?", test_chunks)
    print(f"Answer ({t:.1f}ms): {ans}")
    print(meta)
