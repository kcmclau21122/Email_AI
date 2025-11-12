"""
Test script to verify vector store and embeddings are working correctly.
Run this to diagnose issues with email search functionality.
"""

import sys
from pathlib import Path

print("=" * 60)
print("Email AI - Vector Store Test")
print("=" * 60)

# Test 1: Import dependencies
print("\n[1/5] Testing imports...")
try:
    import chromadb
    print("[OK] chromadb imported successfully")
except ImportError as e:
    print(f"[FAIL] Failed to import chromadb: {e}")
    print("  Fix: pip install chromadb")
    sys.exit(1)

try:
    from sentence_transformers import SentenceTransformer
    print("[OK] sentence-transformers imported successfully")
except ImportError as e:
    print(f"[FAIL] Failed to import sentence-transformers: {e}")
    print("  Fix: pip install sentence-transformers")
    sys.exit(1)

# Test 2: Load embedding model
print("\n[2/5] Loading embedding model...")
try:
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("[OK] Embedding model loaded successfully")
    print(f"  Model: all-MiniLM-L6-v2")
except Exception as e:
    print(f"[FAIL] Failed to load embedding model: {e}")
    sys.exit(1)

# Test 3: Test embeddings
print("\n[3/5] Testing embeddings...")
try:
    test_text = "This is a test email about project updates."
    embedding = model.encode(test_text)
    print(f"[OK] Generated embedding of size {len(embedding)}")
except Exception as e:
    print(f"[FAIL] Failed to generate embedding: {e}")
    sys.exit(1)

# Test 4: Test ChromaDB
print("\n[4/5] Testing ChromaDB...")
try:
    from vector_store import VectorStore

    # Check if chroma_db exists
    chroma_path = Path("chroma_db")
    if chroma_path.exists():
        print(f"[OK] Vector database found at: {chroma_path}")

        # Initialize vector store
        vector_store = VectorStore()
        stats = vector_store.get_collection_stats()
        print(f"[OK] Collection loaded successfully")
        print(f"  Total emails in database: {stats['total_emails']}")

        # Test search if emails exist
        if stats['total_emails'] > 0:
            print("\n[5/5] Testing search...")
            results = vector_store.search("test query", n_results=1)
            if results['documents'] and results['documents'][0]:
                print(f"[OK] Search working! Found {len(results['documents'][0])} results")
            else:
                print("[WARN] Search executed but found no results")
                print("  This could mean embeddings weren't created properly")
        else:
            print("\n[5/5] Skipping search test (no emails in database)")
            print("  Process some emails first using the Streamlit UI")
    else:
        print("[WARN] Vector database not found")
        print("  Process some emails first using the Streamlit UI")
        print("\n[5/5] Skipping search test (no database)")

except Exception as e:
    print(f"[FAIL] Error testing vector store: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)
print("[OK] All core dependencies are working")
print("[OK] Embeddings are functioning correctly")
if chroma_path.exists():
    print(f"[OK] Vector database exists with {stats['total_emails']} emails")
    if stats['total_emails'] == 0:
        print("\n[WARN] RECOMMENDATION:")
        print("  Your vector database is empty. Process some emails to test search.")
    elif stats['total_emails'] > 0 and not (results['documents'] and results['documents'][0]):
        print("\n[WARN] WARNING:")
        print("  Emails are in database but search returns no results.")
        print("  This suggests embeddings weren't created properly.")
        print("\n  SOLUTION:")
        print("  1. Clear the vector database using Streamlit UI or delete 'chroma_db' folder")
        print("  2. Ensure sentence-transformers is installed: pip install sentence-transformers")
        print("  3. Reprocess your emails")
else:
    print("\n[INFO] NEXT STEPS:")
    print("  1. Start the Streamlit app: streamlit run main.py")
    print("  2. Initialize the system")
    print("  3. Process your emails")

print("\n" + "=" * 60)
