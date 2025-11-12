"""
Main Streamlit application for Email AI Assistant.
Provides a web interface for querying emails using local LLM.
"""

import streamlit as st
from pathlib import Path
import time
import os

from email_processor import EmailProcessor
from vector_store import VectorStore
from llm_handler import OllamaHandler
from logger_config import LoggerConfig
from semantic_chunker import SemanticChunker


# Initialize logger
logger = LoggerConfig.get_logger()


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'vector_store' not in st.session_state:
        st.session_state.vector_store = None
    if 'llm_handler' not in st.session_state:
        st.session_state.llm_handler = None
    if 'emails_processed' not in st.session_state:
        st.session_state.emails_processed = False
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'processor' not in st.session_state:
        st.session_state.processor = None


def setup_sidebar():
    """Setup the sidebar with configuration options."""
    with st.sidebar:
        st.title("⚙️ Configuration")

        # Email directory selection
        st.subheader("Email Directory")

        # Quick select for common paths
        quick_paths = {
            "Default (./emails)": "emails",
            "Custom Path": "custom"
        }

        # Add drive letters for Windows
        if os.name == 'nt':  # Windows
            for drive in ['C:', 'D:', 'E:', 'F:', 'G:']:
                if os.path.exists(drive):
                    quick_paths[f"{drive}\\"] = f"{drive}\\"

        path_choice = st.radio(
            "Select Email Location",
            options=list(quick_paths.keys()),
            index=0,
            help="Choose email directory location"
        )

        if quick_paths[path_choice] == "custom":
            email_dir = st.text_input(
                "Enter Custom Path",
                value="emails",
                help="Full path to directory containing email files (.eml, .msg, .mbox)"
            )
        else:
            if quick_paths[path_choice].endswith("\\"):
                # For drive selection, let user add the rest of the path
                email_dir = st.text_input(
                    f"Path on {path_choice}",
                    value=f"{quick_paths[path_choice]}emails",
                    help="Enter the full path to your email directory"
                )
            else:
                email_dir = quick_paths[path_choice]

        st.caption(f"📁 Using: {os.path.abspath(email_dir)}")

        # Ollama settings
        st.subheader("Ollama Settings")
        ollama_url = st.text_input(
            "Ollama URL",
            value="http://localhost:11434",
            help="URL where Ollama is running"
        )

        # Model selection
        if st.session_state.llm_handler:
            available_models = st.session_state.llm_handler.list_models()
            if available_models:
                # Try to default to llama3, otherwise use first model
                default_index = 0
                for i, model in enumerate(available_models):
                    if 'llama3' in model.lower():
                        default_index = i
                        break

                current_model = st.selectbox(
                    "Select Model",
                    options=available_models,
                    index=default_index
                )
                if st.button("Switch Model"):
                    st.session_state.llm_handler.set_model(current_model)
                    st.success(f"Switched to {current_model}")
            else:
                st.warning("No models found. Please pull a model using 'ollama pull llama3'")
        else:
            model_name = st.text_input(
                "Model Name",
                value="llama3",
                help="Ollama model to use (e.g., llama2, mistral, llama3)"
            )

        # Initialize button
        if st.button("Initialize System", type="primary"):
            with st.spinner("Initializing..."):
                try:
                    # Initialize LLM handler
                    if not st.session_state.llm_handler:
                        model = model_name if 'model_name' in locals() else "llama3"
                        st.session_state.llm_handler = OllamaHandler(
                            base_url=ollama_url,
                            model=model
                        )

                    # Check if Ollama is available
                    if not st.session_state.llm_handler.is_available():
                        st.error("⚠️ Cannot connect to Ollama. Make sure it's running with 'ollama serve'")
                        return

                    # Initialize vector store
                    st.session_state.vector_store = VectorStore()

                    st.success("✅ System initialized successfully!")
                    logger.info("System initialized from Streamlit UI")

                except Exception as e:
                    st.error(f"Error initializing system: {str(e)}")
                    logger.error(f"System initialization failed: {str(e)}")

        # Process emails button
        st.subheader("Process Emails")
        if st.button("Load & Process Emails"):
            if not st.session_state.vector_store or not st.session_state.llm_handler:
                st.warning("Please initialize the system first")
            else:
                process_emails(email_dir)

        # Display statistics
        if st.session_state.vector_store:
            st.subheader("Database Statistics")
            stats = st.session_state.vector_store.get_collection_stats()
            st.metric("Total Emails", stats['total_emails'])

            # Show chunk statistics if chunking is enabled
            if stats.get('chunking_enabled'):
                st.metric("Total Chunks", stats.get('total_chunks', 0))
                avg_chunks = stats.get('total_chunks', 0) / max(stats['total_emails'], 1)
                st.caption(f"📊 Avg chunks per email: {avg_chunks:.1f}")

        # Display filter statistics
        if 'processor' in st.session_state and st.session_state.processor:
            filter_stats = st.session_state.processor.get_filter_statistics()
            if filter_stats:
                st.subheader("Filter Statistics")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Checked", filter_stats['total_checked'])
                    st.metric("Passed", filter_stats['passed'])
                with col2:
                    st.metric("Filtered", filter_stats['filtered_out'])
                    st.metric("Whitelisted", filter_stats['whitelisted'])

                # Show filter reasons in expander
                if filter_stats['reasons']:
                    with st.expander("Filter Reasons"):
                        for reason, count in filter_stats['reasons'].items():
                            st.text(f"{reason}: {count}")

        # Clear database option
        if st.session_state.vector_store:
            st.subheader("⚠️ Danger Zone")
            if st.button("Clear All Emails", type="secondary"):
                if st.checkbox("I understand this will delete all processed emails"):
                    st.session_state.vector_store.clear_collection()
                    st.session_state.emails_processed = False
                    st.success("Database cleared")
                    st.rerun()

        return email_dir


def process_emails(email_dir: str):
    """
    Process emails from the specified directory with semantic chunking.

    Args:
        email_dir: Path to email directory
    """
    try:
        with st.spinner("Processing emails..."):
            processor = EmailProcessor(email_dir)
            # Store processor in session state for filter statistics
            st.session_state.processor = processor

            # Get all email files
            email_files = processor.get_email_files()

            if not email_files:
                st.warning(f"No email files found in {email_dir}")
                logger.warning(f"No email files found in {email_dir}")
                return

            # Check if using chunking
            use_chunking = st.session_state.vector_store.use_chunking

            # Initialize chunker if needed
            if use_chunking:
                chunker = SemanticChunker(
                    max_chunk_size=512,
                    min_chunk_size=50,
                    overlap_size=50
                )
                logger.info("Using semantic chunking for email processing")

            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()

            if use_chunking:
                # Process emails with chunking
                all_chunks = []
                for i, email_file in enumerate(email_files):
                    status_text.text(f"Chunking {email_file.name}...")
                    email_data = processor.parse_email(email_file)

                    if email_data:
                        # Chunk the email
                        email_chunks = chunker.chunk_email(email_data)
                        all_chunks.extend(email_chunks)

                    progress_bar.progress((i + 1) / len(email_files))

                # Add chunks to vector store
                if all_chunks:
                    status_text.text("Adding chunks to database...")
                    st.session_state.vector_store.add_chunks_batch(all_chunks)

                progress_bar.empty()
                status_text.empty()

                # Display results with filter statistics
                filter_stats = processor.get_filter_statistics()
                # Count unique emails
                unique_emails = len(set(chunk['metadata']['email_id'] for chunk in all_chunks))

                if filter_stats:
                    st.success(f"✅ Processed {unique_emails} emails into {len(all_chunks)} chunks!")
                    st.info(f"📊 Filter Statistics: {filter_stats['total_checked']} checked, "
                           f"{filter_stats['passed']} passed, {filter_stats['filtered_out']} filtered out")
                else:
                    st.success(f"✅ Processed {unique_emails} emails into {len(all_chunks)} chunks!")

                st.session_state.emails_processed = True
                logger.info(f"Processed {unique_emails} emails into {len(all_chunks)} chunks from UI")

            else:
                # Process emails without chunking (legacy mode)
                emails_to_add = []
                for i, email_file in enumerate(email_files):
                    status_text.text(f"Processing {email_file.name}...")
                    email_data = processor.parse_email(email_file)

                    if email_data:
                        text_content = processor.get_all_text_content(email_data)
                        emails_to_add.append((email_data, text_content))

                    progress_bar.progress((i + 1) / len(email_files))

                # Add to vector store in batch
                if emails_to_add:
                    status_text.text("Adding emails to database...")
                    st.session_state.vector_store.add_emails_batch(emails_to_add)

                progress_bar.empty()
                status_text.empty()

                # Display results with filter statistics
                filter_stats = processor.get_filter_statistics()
                if filter_stats:
                    st.success(f"✅ Processed {len(emails_to_add)} emails successfully!")
                    st.info(f"📊 Filter Statistics: {filter_stats['total_checked']} checked, "
                           f"{filter_stats['passed']} passed, {filter_stats['filtered_out']} filtered out")
                else:
                    st.success(f"✅ Processed {len(emails_to_add)} emails successfully!")

                st.session_state.emails_processed = True
                logger.info(f"Processed {len(emails_to_add)} emails from UI")

    except Exception as e:
        st.error(f"Error processing emails: {str(e)}")
        logger.error(f"Error in process_emails: {str(e)}")


def display_chat_interface():
    """Display the chat interface for querying emails."""
    st.title("📧 Email AI Assistant")
    st.write("Ask questions about your emails and attachments")

    # Check if system is ready
    if not st.session_state.vector_store or not st.session_state.llm_handler:
        st.info("👈 Please initialize the system using the sidebar")
        return

    if not st.session_state.emails_processed:
        stats = st.session_state.vector_store.get_collection_stats()
        if stats['total_emails'] == 0:
            st.info("👈 Please load and process your emails using the sidebar")
            return

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Chat input
    if query := st.chat_input("Ask a question about your emails..."):
        # Add user message to chat
        st.session_state.chat_history.append({"role": "user", "content": query})

        with st.chat_message("user"):
            st.write(query)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Searching emails and generating response..."):
                try:
                    # Get relevant context from vector store
                    context = st.session_state.vector_store.get_context_for_query(
                        query,
                        n_results=3
                    )

                    # Generate response with streaming
                    response_placeholder = st.empty()
                    full_response = ""

                    for chunk in st.session_state.llm_handler.query_with_context_stream(
                        query,
                        context
                    ):
                        full_response += chunk
                        response_placeholder.write(full_response + "▌")

                    response_placeholder.write(full_response)

                    # Add assistant response to chat history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": full_response
                    })

                    logger.info(f"Processed query: {query[:50]}")

                except Exception as e:
                    error_msg = f"Error generating response: {str(e)}"
                    st.error(error_msg)
                    logger.error(error_msg)


def main():
    """Main application entry point."""
    st.set_page_config(
        page_title="Email AI Assistant",
        page_icon="📧",
        layout="wide"
    )

    # Initialize session state
    initialize_session_state()

    # Setup sidebar
    setup_sidebar()

    # Display main chat interface
    display_chat_interface()

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.caption("Email AI Assistant v1.0")
    st.sidebar.caption("Powered by Ollama & ChromaDB")


if __name__ == "__main__":
    logger.info("Starting Email AI Assistant")
    main()
