"""
LLM handler module for interacting with Ollama local language models.
Provides RAG (Retrieval Augmented Generation) capabilities for email querying.
"""

import requests
import json
from typing import Dict, List, Optional, Generator

from logger_config import LoggerConfig, log_function_call


logger = LoggerConfig.get_logger()


class OllamaHandler:
    """Handles interactions with Ollama local LLM."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        """
        Initialize the Ollama handler.

        Args:
            base_url: Ollama API base URL
            model: Model name to use (e.g., 'llama2', 'mistral', 'llama3')
        """
        self.base_url = base_url
        self.model = model
        self.api_generate = f"{base_url}/api/generate"
        self.api_chat = f"{base_url}/api/chat"
        self.api_tags = f"{base_url}/api/tags"

        logger.info(f"OllamaHandler initialized with model: {model}")
        self._check_connection()

    def _check_connection(self):
        """Check if Ollama server is running and accessible."""
        try:
            response = requests.get(self.api_tags, timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                logger.info(f"Successfully connected to Ollama. Available models: {model_names}")

                # Check if selected model is available
                if not any(self.model in name for name in model_names):
                    logger.warning(f"Model '{self.model}' not found in available models. You may need to pull it first.")
            else:
                logger.warning("Could not retrieve Ollama models list")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Ollama server: {str(e)}")
            logger.error("Make sure Ollama is running. Start it with 'ollama serve'")

    @log_function_call
    def generate(self, prompt: str, stream: bool = False) -> str:
        """
        Generate text using Ollama.

        Args:
            prompt: Input prompt
            stream: Whether to stream the response

        Returns:
            Generated text
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": stream
            }

            response = requests.post(
                self.api_generate,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                if stream:
                    # Handle streaming response
                    full_response = ""
                    for line in response.iter_lines():
                        if line:
                            json_response = json.loads(line)
                            full_response += json_response.get('response', '')
                    return full_response
                else:
                    return response.json().get('response', '')
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return "Error generating response from Ollama."

        except Exception as e:
            logger.error(f"Error calling Ollama generate: {str(e)}")
            return f"Error: {str(e)}"

    @log_function_call
    def generate_stream(self, prompt: str) -> Generator[str, None, None]:
        """
        Generate text using Ollama with streaming.

        Args:
            prompt: Input prompt

        Yields:
            Text chunks as they are generated
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": True
            }

            response = requests.post(
                self.api_generate,
                json=payload,
                stream=True,
                timeout=120
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        json_response = json.loads(line)
                        chunk = json_response.get('response', '')
                        if chunk:
                            yield chunk
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                yield "Error generating response from Ollama."

        except Exception as e:
            logger.error(f"Error calling Ollama generate_stream: {str(e)}")
            yield f"Error: {str(e)}"

    @log_function_call
    def query_with_context(self, query: str, context: str, stream: bool = False) -> str:
        """
        Query the LLM with relevant email context (RAG pattern).

        Args:
            query: User question
            context: Relevant email context
            stream: Whether to stream the response

        Returns:
            LLM response
        """
        prompt = f"""You are an AI assistant that helps answer questions about emails and their attachments.

Context from relevant emails:
{context}

User question: {query}

Please provide a helpful and accurate answer based on the email context provided above. If the context doesn't contain enough information to answer the question, please say so."""

        return self.generate(prompt, stream=stream)

    @log_function_call
    def query_with_context_stream(self, query: str, context: str) -> Generator[str, None, None]:
        """
        Query the LLM with relevant email context and stream the response.

        Args:
            query: User question
            context: Relevant email context

        Yields:
            Response text chunks
        """
        prompt = f"""You are an AI assistant that helps answer questions about emails and their attachments.

Context from relevant emails:
{context}

User question: {query}

Please provide a helpful and accurate answer based on the email context provided above. If the context doesn't contain enough information to answer the question, please say so."""

        yield from self.generate_stream(prompt)

    @log_function_call
    def list_models(self) -> List[str]:
        """
        Get list of available Ollama models.

        Returns:
            List of model names
        """
        try:
            response = requests.get(self.api_tags, timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [m['name'] for m in models]
            return []
        except Exception as e:
            logger.error(f"Error listing models: {str(e)}")
            return []

    @log_function_call
    def set_model(self, model: str):
        """
        Change the active model.

        Args:
            model: Model name to switch to
        """
        self.model = model
        logger.info(f"Switched to model: {model}")

    def is_available(self) -> bool:
        """
        Check if Ollama service is available.

        Returns:
            True if available, False otherwise
        """
        try:
            response = requests.get(self.api_tags, timeout=5)
            return response.status_code == 200
        except:
            return False
