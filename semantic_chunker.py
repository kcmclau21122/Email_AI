"""
Semantic chunking module for breaking emails into meaningful segments.
Improves vector search accuracy by creating focused, contextual chunks.
"""

import re
from typing import List, Dict, Tuple
from logger_config import LoggerConfig, log_function_call

logger = LoggerConfig.get_logger()


class SemanticChunker:
    """Handles semantic chunking of email content."""

    def __init__(self,
                 max_chunk_size: int = 512,
                 min_chunk_size: int = 50,
                 overlap_size: int = 50):
        """
        Initialize semantic chunker.

        Args:
            max_chunk_size: Maximum characters per chunk
            min_chunk_size: Minimum characters per chunk
            overlap_size: Overlap between chunks for context continuity
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_size = overlap_size
        logger.info(f"SemanticChunker initialized (max={max_chunk_size}, min={min_chunk_size}, overlap={overlap_size})")

    @log_function_call
    def chunk_email(self, email_data: Dict) -> List[Dict]:
        """
        Break an email into semantic chunks.

        Args:
            email_data: Email data dictionary

        Returns:
            List of chunk dictionaries with content and metadata
        """
        chunks = []
        email_id = email_data['file_path']  # Use file path as unique email ID

        # Chunk 1: Email metadata (always first chunk - provides context)
        metadata_chunk = self._create_metadata_chunk(email_data, email_id, 0)
        chunks.append(metadata_chunk)

        # Chunk 2+: Body content (if exists and not empty)
        body = email_data.get('body', '').strip()
        if body and len(body) >= self.min_chunk_size:
            body_chunks = self._chunk_body(body, email_data, email_id, start_index=1)
            chunks.extend(body_chunks)

        # Chunk N+: Attachments (each attachment is a separate chunk)
        attachment_chunks = self._chunk_attachments(
            email_data.get('attachments', []),
            email_data,
            email_id,
            start_index=len(chunks)
        )
        chunks.extend(attachment_chunks)

        logger.debug(f"Email chunked into {len(chunks)} segments: {email_id}")
        return chunks

    def _create_metadata_chunk(self, email_data: Dict, email_id: str, index: int) -> Dict:
        """Create a metadata chunk containing email headers and context."""
        # Build focused metadata content
        content_parts = [
            f"Subject: {email_data['subject']}",
            f"From: {email_data['from']}",
            f"To: {email_data['to']}",
            f"Date: {email_data['date']}"
        ]

        # Add brief summary if body exists
        body = email_data.get('body', '').strip()
        if body:
            # Extract first sentence or first 200 chars for context
            first_sentence = self._extract_first_sentence(body)
            if first_sentence:
                content_parts.append(f"Preview: {first_sentence}")

        # Add attachment info if exists
        attachments = email_data.get('attachments', [])
        if attachments:
            attachment_names = [att['filename'] for att in attachments]
            content_parts.append(f"Attachments: {', '.join(attachment_names)}")

        return {
            'content': '\n'.join(content_parts),
            'metadata': {
                'email_id': email_id,
                'chunk_type': 'metadata',
                'chunk_index': index,
                'subject': email_data['subject'][:500],
                'from': email_data['from'][:200],
                'to': email_data['to'][:200],
                'date': str(email_data['date'])[:100],
                'num_attachments': len(attachments)
            }
        }

    def _chunk_body(self, body: str, email_data: Dict, email_id: str, start_index: int) -> List[Dict]:
        """
        Chunk email body content intelligently.

        Strategy:
        1. Try to split by paragraphs first (natural semantic boundaries)
        2. If paragraphs are too large, split by sentences
        3. If still too large, split by character count with overlap
        """
        chunks = []

        # Clean body (remove excessive whitespace, but preserve structure)
        body = self._clean_body(body)

        # Check if body is HTML
        is_html = body.strip().startswith('<') or '<html' in body[:200].lower()

        if is_html:
            # For HTML, extract text and split more aggressively
            text_content = self._extract_text_from_html(body)
            if text_content:
                body = text_content

        # Split by paragraphs (double newline or <br> tags)
        paragraphs = re.split(r'\n\n+|\r\n\r\n+', body)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        current_chunk = ""
        chunk_index = start_index

        for para in paragraphs:
            # If paragraph itself is too large, split it
            if len(para) > self.max_chunk_size:
                # Flush current chunk if exists
                if current_chunk:
                    chunks.append(self._create_body_chunk(
                        current_chunk, email_data, email_id, chunk_index
                    ))
                    chunk_index += 1
                    current_chunk = ""

                # Split large paragraph by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) > self.max_chunk_size:
                        if current_chunk:
                            chunks.append(self._create_body_chunk(
                                current_chunk, email_data, email_id, chunk_index
                            ))
                            chunk_index += 1
                            # Add overlap from end of previous chunk
                            current_chunk = current_chunk[-self.overlap_size:] + " " + sentence
                        else:
                            current_chunk = sentence
                    else:
                        current_chunk += " " + sentence if current_chunk else sentence
            else:
                # Normal paragraph, try to add to current chunk
                if len(current_chunk) + len(para) > self.max_chunk_size:
                    # Chunk is full, save it
                    chunks.append(self._create_body_chunk(
                        current_chunk, email_data, email_id, chunk_index
                    ))
                    chunk_index += 1
                    # Start new chunk with overlap
                    current_chunk = current_chunk[-self.overlap_size:] + "\n\n" + para
                else:
                    current_chunk += "\n\n" + para if current_chunk else para

        # Add final chunk if exists
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(self._create_body_chunk(
                current_chunk, email_data, email_id, chunk_index
            ))

        return chunks

    def _create_body_chunk(self, content: str, email_data: Dict, email_id: str, index: int) -> Dict:
        """Create a body content chunk."""
        return {
            'content': content.strip(),
            'metadata': {
                'email_id': email_id,
                'chunk_type': 'body',
                'chunk_index': index,
                'subject': email_data['subject'][:500],
                'from': email_data['from'][:200],
                'date': str(email_data['date'])[:100]
            }
        }

    def _chunk_attachments(self, attachments: List[Dict], email_data: Dict,
                          email_id: str, start_index: int) -> List[Dict]:
        """Create chunks for email attachments."""
        chunks = []

        for i, attachment in enumerate(attachments):
            # Only chunk attachments with text content
            text_content = attachment.get('text_content', '').strip()
            if not text_content or len(text_content) < self.min_chunk_size:
                continue

            # For very large attachments, split into multiple chunks
            if len(text_content) > self.max_chunk_size:
                # Split large attachment
                att_chunks = self._split_large_text(text_content)
                for j, chunk_text in enumerate(att_chunks):
                    chunks.append({
                        'content': f"Attachment: {attachment['filename']}\n\n{chunk_text}",
                        'metadata': {
                            'email_id': email_id,
                            'chunk_type': 'attachment',
                            'chunk_index': start_index + len(chunks),
                            'attachment_name': attachment['filename'],
                            'attachment_part': j + 1,
                            'subject': email_data['subject'][:500],
                            'from': email_data['from'][:200],
                            'date': str(email_data['date'])[:100]
                        }
                    })
            else:
                # Single chunk for smaller attachment
                chunks.append({
                    'content': f"Attachment: {attachment['filename']}\n\n{text_content}",
                    'metadata': {
                        'email_id': email_id,
                        'chunk_type': 'attachment',
                        'chunk_index': start_index + len(chunks),
                        'attachment_name': attachment['filename'],
                        'subject': email_data['subject'][:500],
                        'from': email_data['from'][:200],
                        'date': str(email_data['date'])[:100]
                    }
                })

        return chunks

    def _split_large_text(self, text: str) -> List[str]:
        """Split large text into chunks with overlap."""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + self.max_chunk_size

            # If not at the end, try to break at a sentence or word boundary
            if end < text_len:
                # Look for sentence end
                sentence_end = text.rfind('.', start, end)
                if sentence_end > start + self.min_chunk_size:
                    end = sentence_end + 1
                else:
                    # Look for word boundary
                    space = text.rfind(' ', start, end)
                    if space > start + self.min_chunk_size:
                        end = space

            chunks.append(text[start:end].strip())
            start = end - self.overlap_size if end < text_len else text_len

        return chunks

    def _clean_body(self, body: str) -> str:
        """Clean body text while preserving structure."""
        # Remove excessive blank lines (more than 2)
        body = re.sub(r'\n{3,}', '\n\n', body)
        # Remove excessive spaces
        body = re.sub(r' {2,}', ' ', body)
        return body.strip()

    def _extract_first_sentence(self, text: str) -> str:
        """Extract first meaningful sentence from text."""
        # Try to find first sentence
        match = re.search(r'^[^.!?]{10,}[.!?]', text)
        if match:
            return match.group(0).strip()

        # Fallback to first 200 chars
        return text[:200].strip() + "..." if len(text) > 200 else text.strip()

    def _extract_text_from_html(self, html: str) -> str:
        """
        Extract plain text from HTML.
        Simple approach - remove tags and decode entities.
        """
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)

        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')
        text = text.replace('&quot;', '"')

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()
