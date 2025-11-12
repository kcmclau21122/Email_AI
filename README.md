# Email AI Assistant

An intelligent email analysis system that uses local LLMs (via Ollama) to answer questions about your emails and attachments. Built with Streamlit for an intuitive web interface and ChromaDB for efficient vector search.

## Features

- **Local LLM Processing**: Uses Ollama for private, local AI processing
- **Email & Attachment Analysis**: Processes emails (.eml, .msg, .mbox) and attachments (PDF, DOCX, TXT)
- **ProtonMail Support**: Native support for ProtonMail exports with metadata.json files
- **Semantic Chunking**: Breaks emails into focused segments for improved search accuracy
- **Smart Filtering**: Filter emails by sender, domain, subject, labels, date range, and more
- **RAG (Retrieval Augmented Generation)**: Semantic search across your email database
- **GPU Acceleration**: Supports NVIDIA GPUs for faster processing
- **Incremental Updates**: Add new emails without reprocessing everything
- **Comprehensive Logging**: All critical functions are logged with timestamps
- **Filter Statistics**: Track how many emails are filtered and why

## System Requirements

- Python 3.13
- NVIDIA GeForce RTX GPU with 16GB RAM (CUDA 12.1+)
- Ollama installed and running
- Windows, Linux, or macOS

## Installation

### 1. Create Virtual Environment

Using Python 3.13 from your specific installation:

```bash
# Create virtual environment
C:\Users\mclau\AppData\Local\Programs\Python\Python313\python.exe -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On Linux/Mac:
# source venv/bin/activate
```

### 2. Install Dependencies

```bash
# Install core dependencies (includes sentence-transformers for embeddings)
pip install -r requirements.txt

# Install GPU support (CUDA 12.1+)
pip install -r requirements-gpu-cu121.txt --extra-index-url https://download.pytorch.org/whl/cu121
```

**Important:** The `sentence-transformers` package is required for generating embeddings. It will download the `all-MiniLM-L6-v2` model (~80MB) on first use.

### 3. Install Ollama

Download and install Ollama from [https://ollama.ai/](https://ollama.ai/)

After installation, pull a model:

```bash
# Start Ollama server
ollama serve

# In another terminal, pull a model (choose one):
ollama pull llama2        # Recommended for general use
ollama pull llama3        # Latest version (requires more resources)
ollama pull mistral       # Fast and efficient
ollama pull codellama     # Good for technical content
```

## Project Structure

```
Email_AI/
├── main.py                          # Main Streamlit application
├── email_processor.py               # Email parsing, filtering, and attachment extraction
├── vector_store.py                  # ChromaDB vector database management
├── llm_handler.py                   # Ollama LLM interface
├── logger_config.py                 # Logging configuration
├── email_filters.json               # Email filtering configuration
├── requirements.txt                 # Core Python dependencies
├── requirements-gpu-cu121.txt       # GPU-specific dependencies
├── .gitignore                       # Git ignore rules
├── README.md                        # This file
├── logs/                            # Application logs (auto-created)
│   └── email_ai_YYYYMMDD_HHMMSS.log
├── chroma_db/                       # Vector database (auto-created)
└── emails/                          # Your email files (create this)
    └── [email].eml                  # Email file
    └── [email].metadata.json        # ProtonMail metadata (optional)
```

## Usage

### 1. Prepare Your Emails

Create an `emails` directory and place your ProtonMail export files there:

```bash
mkdir emails
# Copy your .eml, .msg, or .mbox files to this directory
```

### 2. Start the Application

```bash
# Make sure your virtual environment is activated
# Make sure Ollama is running (ollama serve)

streamlit run main.py
```

The application will open in your default browser at `http://localhost:8501`

### 3. Using the Application

1. **Initialize System**:
   - Configure the email directory path (default: `emails`)
   - Select your Ollama model
   - Click "Initialize System"

2. **Process Emails**:
   - Click "Load & Process Emails"
   - Wait for the processing to complete
   - The system will extract text from emails and attachments

3. **Ask Questions**:
   - Type your question in the chat input
   - The system will search relevant emails and generate responses
   - Examples:
     - "What emails did I receive about project deadlines?"
     - "Summarize the contract in the attachment from John"
     - "Find all emails mentioning budget approval"

### 4. Adding New Emails

To add new emails without reprocessing everything:

1. Add new email files to your `emails` directory
2. Click "Load & Process Emails" again
3. The system will only process new emails (duplicates are skipped)

## Configuration

### Semantic Chunking (Enabled by Default)

The system uses semantic chunking to improve search accuracy by breaking emails into focused segments:

**How it Works:**
1. **Metadata Chunk**: Contains subject, from, to, date, and email preview
2. **Body Chunks**: Email body split into semantic segments (paragraphs, sections)
3. **Attachment Chunks**: Each attachment becomes a separate searchable chunk

**Benefits:**
- **Better Search Results**: Finds specific information within long emails
- **Improved Relevance**: Matches query to the most relevant part of an email
- **HTML Handling**: Automatically extracts text from HTML emails
- **Context Preservation**: Overlapping chunks maintain context continuity

**Chunking Parameters** (configured in [main.py:217-221](main.py#L217-L221)):
- `max_chunk_size`: 512 characters (optimal for embeddings)
- `min_chunk_size`: 50 characters (filters out tiny chunks)
- `overlap_size`: 50 characters (maintains context between chunks)

**Statistics:**
- View chunk statistics in the Streamlit sidebar
- See "Total Chunks" and average chunks per email
- Typical ratio: 2-5 chunks per email

### Email Filtering

The system supports advanced email filtering through the `email_filters.json` configuration file. This allows you to exclude unwanted emails (newsletters, notifications, etc.) from training your AI model.

#### Filter Configuration File

Edit `email_filters.json` to customize your filters:

```json
{
  "filters": {
    "ignore_senders": {
      "enabled": true,
      "addresses": ["notifications@example.com", "noreply@example.com"],
      "domains": ["discoursemail.com", "newsletter.com"]
    },
    "ignore_sender_names": {
      "enabled": true,
      "names": ["DeepLearning.AI", "Newsletter", "Marketing Team"]
    },
    "ignore_subjects": {
      "enabled": false,
      "keywords": ["unsubscribe", "newsletter", "promotional"]
    },
    "ignore_label_ids": {
      "enabled": false,
      "label_ids": ["4", "8"]
    },
    "require_attachments": {
      "enabled": false
    },
    "date_range": {
      "enabled": false,
      "start_date": 1609459200,
      "end_date": 1640995200
    }
  },
  "whitelist": {
    "enabled": false,
    "sender_addresses": ["important@example.com"],
    "sender_domains": ["company.com"]
  }
}
```

#### Filter Types

1. **ignore_senders**: Block specific email addresses or entire domains
   - `addresses`: List of exact email addresses to ignore
   - `domains`: List of domains to ignore (e.g., "discoursemail.com")

2. **ignore_sender_names**: Block by sender display name (case-insensitive partial match)
   - Useful for filtering newsletters by sender name

3. **ignore_subjects**: Block emails containing specific keywords in subject
   - Case-insensitive partial match

4. **ignore_label_ids**: Block ProtonMail emails by label ID
   - Common labels: 4 = Spam, 8 = Trash (check your ProtonMail export)

5. **require_attachments**: Only process emails that have attachments
   - Useful if you only want to train on emails with documents

6. **date_range**: Only process emails within a date range
   - Uses Unix timestamps
   - Set `start_date` and/or `end_date`

7. **whitelist**: Override all filters for important senders
   - Whitelisted emails are always processed
   - Can whitelist by address or domain

#### Using Filters

1. **Edit the filter configuration**:
   ```bash
   # Open email_filters.json in your editor
   notepad email_filters.json
   ```

2. **Enable/disable filters**:
   - Set `"enabled": true` to activate a filter
   - Set `"enabled": false` to deactivate

3. **Add your filter rules**:
   - Add email addresses, domains, or keywords to the appropriate lists
   - Use lowercase for consistency

4. **Process emails**:
   - Filters are automatically applied when you click "Load & Process Emails"
   - View filter statistics in the sidebar

#### ProtonMail Metadata

For ProtonMail exports, the system automatically reads `.metadata.json` files that contain:
- Sender information (name and address)
- Subject line
- Label IDs
- Date/time
- Attachment count
- Link to original email

This metadata enables more accurate filtering than parsing email headers alone.

### Changing Models

You can switch models in the sidebar:
- Select from available models
- Click "Switch Model"

### Database Management

- **View Statistics**: Check total emails processed in the sidebar
- **Filter Statistics**: View how many emails were checked, passed, filtered, and whitelisted
- **Filter Reasons**: Expand to see detailed breakdown of why emails were filtered
- **Clear Database**: Use the "Clear All Emails" button (with confirmation)

## GPU Utilization

The application automatically utilizes your NVIDIA GPU for:
- PyTorch operations (if using embedding models)
- Ollama inference (Ollama automatically detects and uses GPU)

To verify GPU usage:
```bash
# Check NVIDIA GPU utilization
nvidia-smi
```

## Logging

All critical functions are logged to `logs/email_ai_YYYYMMDD_HHMMSS.log`

Log levels:
- **INFO**: Normal operations and status updates
- **DEBUG**: Detailed processing information
- **ERROR**: Errors and exceptions with stack traces

View logs:
```bash
# View latest log file
cat logs/email_ai_*.log | tail -n 50
```

## Troubleshooting

### Vector Search Not Finding Emails ("No relevant emails found")

If the system processes emails but can't find them when querying, this is usually due to missing embedding dependencies:

**Solution:**
1. **Install sentence-transformers** (if not already installed):
   ```bash
   pip install sentence-transformers
   ```

2. **Clear the old vector database**:
   - In the Streamlit UI, go to "Danger Zone" in sidebar
   - Click "Clear All Emails" and confirm
   - Or manually delete the `chroma_db` folder

3. **Reinstall requirements**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Reprocess your emails**:
   - Click "Load & Process Emails" in the UI
   - This will rebuild the vector database with proper embeddings

**Verify embeddings are working:**
```bash
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); print('Embeddings working!')"
```

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve
```

### GPU Not Detected

```bash
# Verify CUDA installation
nvidia-smi

# Check PyTorch GPU support
python -c "import torch; print(torch.cuda.is_available())"
```

### Email Processing Errors

- Ensure email files are valid .eml, .msg, or .mbox format
- Check logs for detailed error messages
- Verify file permissions
- For ProtonMail exports, ensure both .eml and .metadata.json files are present

### Out of Memory

If processing large numbers of emails:
- Process in smaller batches
- Use a smaller Ollama model
- Increase system RAM/VRAM if possible
- Consider using a smaller embedding model

## Advanced Usage

### Using Different Email Directories

In the sidebar, change the "Email Directory" field to point to different email folders.

### Custom Ollama URL

If running Ollama on a different machine or port:
- Update the "Ollama URL" in the sidebar
- Format: `http://hostname:port`

### Programmatic Usage

You can also use the modules programmatically:

```python
from email_processor import EmailProcessor
from vector_store import VectorStore
from llm_handler import OllamaHandler

# Initialize components
processor = EmailProcessor("emails")
vector_store = VectorStore()
llm = OllamaHandler(model="llama2")

# Process emails
emails = processor.process_all_emails()
for email_data in emails:
    text = processor.get_all_text_content(email_data)
    vector_store.add_email(email_data, text)

# Query
query = "Find emails about budget"
context = vector_store.get_context_for_query(query)
response = llm.query_with_context(query, context)
print(response)
```

## Security & Privacy

- **All processing is local**: No data leaves your machine
- **Emails are not uploaded**: Everything stays on your computer
- **Ollama runs locally**: No external API calls
- **Sensitive files**: Add `.env` files or credentials to `.gitignore`

## Contributing

This is a personal project, but suggestions and improvements are welcome.

## License

This project is provided as-is for personal use.

## Support

For issues:
1. Check the logs in `logs/` directory
2. Verify Ollama is running
3. Ensure all dependencies are installed
4. Check that email files are in supported formats

## Version History

- **v1.0** (2025): Initial release
  - Email processing with attachment support
  - RAG-based querying with Ollama
  - Streamlit web interface
  - GPU acceleration support
  - Comprehensive logging

---

Built with Python, Streamlit, Ollama, and ChromaDB
