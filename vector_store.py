"""
Vector store module for managing email embeddings and similarity search.
Uses ChromaDB for efficient vector storage and retrieval.
Supports semantic chunking for improved search accuracy.
"""

import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Optional
import hashlib
from collections import defaultdict

from logger_config import LoggerConfig, log_function_call


logger = LoggerConfig.get_logger()


class VectorStore:
    """Manages vector embeddings and similarity search for email content with semantic chunking."""

    def __init__(self, persist_directory: str = "chroma_db", use_chunking: bool = True):
        """
        Initialize the vector store.

        Args:
            persist_directory: Directory to persist the vector database
            use_chunking: Whether to use semantic chunking (default: True)
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(exist_ok=True)
        self.use_chunking = use_chunking

        logger.info(f"Initializing ChromaDB in: {persist_directory} (chunking={'enabled' if use_chunking else 'disabled'})")

        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Get or create collection for emails
        collection_name = "email_chunks" if use_chunking else "email_collection"
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Email content embeddings (chunked)" if use_chunking else "Email content embeddings"}
        )

        logger.info(f"Collection '{collection_name}' initialized with {self.collection.count()} documents")

    @log_function_call
    def add_email(self, email_data: Dict, text_content: str):
        """
        Add an email to the vector store.

        Args:
            email_data: Email metadata dictionary
            text_content: Combined text content from email and attachments
        """
        try:
            # Create a unique ID for the email using file path hash
            email_id = self._generate_email_id(email_data['file_path'])

            # Check if email already exists
            existing = self.collection.get(ids=[email_id])
            if existing['ids']:
                logger.debug(f"Email already in database: {email_id}")
                return

            # Prepare metadata
            metadata = {
                'subject': email_data['subject'][:500],  # Limit length
                'from': email_data['from'][:200],
                'to': email_data['to'][:200],
                'date': str(email_data['date'])[:100],  # Convert to string first
                'file_path': email_data['file_path'],
                'num_attachments': len(email_data['attachments'])
            }

            # Add to collection
            self.collection.add(
                documents=[text_content],
                metadatas=[metadata],
                ids=[email_id]
            )

            logger.info(f"Added email to vector store: {email_data['subject'][:50]}")

        except Exception as e:
            logger.error(f"Error adding email to vector store: {str(e)}")
            raise

    @log_function_call
    def add_emails_batch(self, emails_data: List[tuple], batch_size: int = 5000):
        """
        Add multiple emails to the vector store in batch.
        Automatically chunks large batches to stay under ChromaDB limits.

        Args:
            emails_data: List of tuples (email_data, text_content)
            batch_size: Maximum number of emails per batch (default: 5000)
        """
        documents = []
        metadatas = []
        ids = []
        total_added = 0

        for email_data, text_content in emails_data:
            try:
                email_id = self._generate_email_id(email_data['file_path'])

                # Check if already exists
                existing = self.collection.get(ids=[email_id])
                if existing['ids']:
                    continue

                metadata = {
                    'subject': email_data['subject'][:500],
                    'from': email_data['from'][:200],
                    'to': email_data['to'][:200],
                    'date': str(email_data['date'])[:100],  # Convert to string first
                    'file_path': email_data['file_path'],
                    'num_attachments': len(email_data['attachments'])
                }

                documents.append(text_content)
                metadatas.append(metadata)
                ids.append(email_id)

                # Add in chunks when we reach batch_size
                if len(documents) >= batch_size:
                    self.collection.add(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                    total_added += len(documents)
                    logger.info(f"Added batch of {len(documents)} emails (total so far: {total_added})")

                    # Reset lists for next batch
                    documents = []
                    metadatas = []
                    ids = []

            except Exception as e:
                logger.error(f"Error preparing email for batch: {str(e)}")
                continue

        # Add remaining documents
        if documents:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            total_added += len(documents)
            logger.info(f"Added final batch of {len(documents)} emails")

        if total_added > 0:
            logger.info(f"Completed batch processing: added {total_added} total emails to vector store")

    @log_function_call
    def search(self, query: str, n_results: int = 5) -> Dict:
        """
        Search for relevant emails based on query.

        Args:
            query: Search query text
            n_results: Number of results to return

        Returns:
            Dictionary containing search results
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, self.collection.count())
            )

            logger.info(f"Search completed for query: '{query[:50]}...', found {len(results['documents'][0])} results")
            return results

        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            return {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}

    @log_function_call
    def get_collection_stats(self) -> Dict:
        """
        Get statistics about the vector store collection.

        Returns:
            Dictionary with collection statistics
        """
        count = self.collection.count()

        if self.use_chunking:
            # Count unique emails (not chunks)
            try:
                all_data = self.collection.get()
                unique_emails = set()
                if all_data['metadatas']:
                    for metadata in all_data['metadatas']:
                        unique_emails.add(metadata.get('email_id', ''))

                stats = {
                    'total_emails': len(unique_emails),
                    'total_chunks': count,
                    'collection_name': self.collection.name,
                    'persist_directory': str(self.persist_directory),
                    'chunking_enabled': True
                }
            except Exception as e:
                logger.error(f"Error counting unique emails: {str(e)}")
                stats = {
                    'total_emails': count,  # Fallback
                    'total_chunks': count,
                    'collection_name': self.collection.name,
                    'persist_directory': str(self.persist_directory),
                    'chunking_enabled': True
                }
        else:
            stats = {
                'total_emails': count,
                'collection_name': self.collection.name,
                'persist_directory': str(self.persist_directory),
                'chunking_enabled': False
            }

        logger.info(f"Collection stats: {stats}")
        return stats

    @log_function_call
    def clear_collection(self):
        """
        Clear all documents from the collection.
        Use with caution!
        """
        collection_name = self.collection.name
        logger.warning(f"Clearing all documents from collection: {collection_name}")

        self.client.delete_collection(name=collection_name)
        self.collection = self.client.create_collection(
            name=collection_name,
            metadata={"description": "Email content embeddings (chunked)" if self.use_chunking else "Email content embeddings"}
        )
        logger.info(f"Collection '{collection_name}' cleared and recreated")

    @log_function_call
    def add_chunks_batch(self, chunks_data: List[Dict], batch_size: int = 5000):
        """
        Add multiple email chunks to the vector store in batch.

        Args:
            chunks_data: List of chunk dictionaries with 'content' and 'metadata'
            batch_size: Maximum number of chunks per batch (default: 5000)
        """
        documents = []
        metadatas = []
        ids = []
        total_added = 0
        skipped = 0

        for chunk in chunks_data:
            try:
                # Generate unique ID for chunk
                chunk_id = self._generate_chunk_id(
                    chunk['metadata']['email_id'],
                    chunk['metadata']['chunk_index']
                )

                # Check if already exists
                existing = self.collection.get(ids=[chunk_id])
                if existing['ids']:
                    skipped += 1
                    continue

                documents.append(chunk['content'])
                metadatas.append(chunk['metadata'])
                ids.append(chunk_id)

                # Add in batches when we reach batch_size
                if len(documents) >= batch_size:
                    self.collection.add(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                    total_added += len(documents)
                    logger.info(f"Added batch of {len(documents)} chunks (total so far: {total_added})")

                    # Reset lists for next batch
                    documents = []
                    metadatas = []
                    ids = []

            except Exception as e:
                logger.error(f"Error preparing chunk for batch: {str(e)}")
                continue

        # Add remaining chunks
        if documents:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            total_added += len(documents)
            logger.info(f"Added final batch of {len(documents)} chunks")

        if total_added > 0:
            logger.info(f"Completed batch processing: added {total_added} chunks ({skipped} skipped as duplicates)")

    @log_function_call
    def search_chunks(self, query: str, n_results: int = 10) -> Dict:
        """
        Search for relevant chunks based on query.
        Returns more results than traditional search since chunks are smaller.

        Args:
            query: Search query text
            n_results: Number of chunk results to return

        Returns:
            Dictionary containing search results grouped by email
        """
        try:
            # Get chunk results
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, self.collection.count())
            )

            if not results['documents'][0]:
                logger.info(f"No chunks found for query: '{query[:50]}...'")
                return {'emails': [], 'total_chunks': 0}

            # Group chunks by email_id
            emails_map = defaultdict(lambda: {
                'chunks': [],
                'metadata': None,
                'best_distance': float('inf')
            })

            for doc, metadata, distance in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ):
                email_id = metadata['email_id']
                emails_map[email_id]['chunks'].append({
                    'content': doc,
                    'type': metadata.get('chunk_type', 'unknown'),
                    'index': metadata.get('chunk_index', 0),
                    'distance': distance
                })

                # Track best distance for ranking
                if distance < emails_map[email_id]['best_distance']:
                    emails_map[email_id]['best_distance'] = distance
                    emails_map[email_id]['metadata'] = metadata

            # Sort emails by best chunk match
            sorted_emails = sorted(
                emails_map.items(),
                key=lambda x: x[1]['best_distance']
            )

            # Format results
            email_results = []
            for email_id, data in sorted_emails:
                # Sort chunks by index
                sorted_chunks = sorted(data['chunks'], key=lambda x: x['index'])

                email_results.append({
                    'email_id': email_id,
                    'subject': data['metadata'].get('subject', 'N/A'),
                    'from': data['metadata'].get('from', 'N/A'),
                    'date': data['metadata'].get('date', 'N/A'),
                    'chunks': sorted_chunks,
                    'best_match_distance': data['best_distance']
                })

            logger.info(f"Search found {len(email_results)} emails with {len(results['documents'][0])} relevant chunks")
            return {
                'emails': email_results,
                'total_chunks': len(results['documents'][0])
            }

        except Exception as e:
            logger.error(f"Error searching chunks: {str(e)}")
            return {'emails': [], 'total_chunks': 0}

    def _generate_email_id(self, file_path: str) -> str:
        """
        Generate a unique ID for an email based on its file path.

        Args:
            file_path: Path to the email file

        Returns:
            Unique hash ID
        """
        return hashlib.md5(file_path.encode()).hexdigest()

    def _generate_chunk_id(self, email_id: str, chunk_index: int) -> str:
        """
        Generate a unique ID for a chunk.

        Args:
            email_id: Email identifier
            chunk_index: Index of the chunk within the email

        Returns:
            Unique chunk ID
        """
        return f"{email_id}_chunk_{chunk_index}"

    def get_context_for_query(self, query: str, n_results: int = 3) -> str:
        """
        Get relevant context for a query by searching the vector store.
        Adapts behavior based on whether chunking is enabled.

        Args:
            query: User query
            n_results: Number of relevant emails to retrieve

        Returns:
            Formatted context string
        """
        if self.use_chunking:
            # Use chunk-based search
            results = self.search_chunks(query, n_results=n_results*3)  # Get more chunks

            if not results['emails']:
                return "No relevant emails found."

            context_parts = []
            for i, email in enumerate(results['emails'][:n_results]):  # Limit to n_results emails
                context_parts.append(f"\n--- Email {i+1} ---")
                context_parts.append(f"Subject: {email['subject']}")
                context_parts.append(f"From: {email['from']}")
                context_parts.append(f"Date: {email['date']}")
                context_parts.append(f"\nRelevant Content:")

                # Include the most relevant chunks
                for chunk in email['chunks'][:3]:  # Top 3 chunks per email
                    context_parts.append(f"\n[{chunk['type']}]")
                    context_parts.append(chunk['content'][:800])  # Limit chunk length

            return "\n".join(context_parts)
        else:
            # Use traditional full-document search
            results = self.search(query, n_results)

            if not results['documents'][0]:
                return "No relevant emails found."

            context_parts = []
            for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
                context_parts.append(f"\n--- Email {i+1} ---")
                context_parts.append(f"Subject: {metadata.get('subject', 'N/A')}")
                context_parts.append(f"From: {metadata.get('from', 'N/A')}")
                context_parts.append(f"Date: {metadata.get('date', 'N/A')}")
                context_parts.append(f"\nContent:\n{doc[:1000]}...")  # Limit content length

            return "\n".join(context_parts)
