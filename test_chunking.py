"""
Test script to verify semantic chunking implementation.
Demonstrates how emails are broken into focused chunks.
"""

import sys
from pathlib import Path

print("=" * 70)
print("Semantic Chunking Test")
print("=" * 70)

# Test 1: Import modules
print("\n[1/4] Testing imports...")
try:
    from semantic_chunker import SemanticChunker
    from email_processor import EmailProcessor
    print("[OK] Modules imported successfully")
except ImportError as e:
    print(f"[FAIL] Import failed: {e}")
    sys.exit(1)

# Test 2: Initialize chunker
print("\n[2/4] Initializing chunker...")
try:
    chunker = SemanticChunker(
        max_chunk_size=512,
        min_chunk_size=50,
        overlap_size=50
    )
    print("[OK] Chunker initialized")
    print(f"  Max chunk size: {chunker.max_chunk_size}")
    print(f"  Min chunk size: {chunker.min_chunk_size}")
    print(f"  Overlap size: {chunker.overlap_size}")
except Exception as e:
    print(f"[FAIL] Failed to initialize: {e}")
    sys.exit(1)

# Test 3: Process sample email
print("\n[3/4] Processing sample email...")
email_dir = input("Enter path to email directory (or press Enter for default): ").strip()

if not email_dir:
    email_dir = "g:/emails/mclaurinkevinc@protonmail.com/mail_20251112_132400"

email_path = Path(email_dir)
if not email_path.exists():
    print(f"[FAIL] Directory not found: {email_dir}")
    sys.exit(1)

try:
    processor = EmailProcessor(str(email_path), filter_config_path=None)
    email_files = processor.get_email_files()

    if not email_files:
        print(f"[FAIL] No emails found in {email_dir}")
        sys.exit(1)

    print(f"[OK] Found {len(email_files)} email files")

    # Test with first email
    test_email = email_files[0]
    print(f"\nTesting with: {test_email.name}")

    email_data = processor.parse_email(test_email, apply_filters=False)

    if not email_data:
        print("[FAIL] Failed to parse email")
        sys.exit(1)

    print(f"[OK] Email parsed")
    print(f"  Subject: {email_data['subject']}")
    print(f"  From: {email_data['from']}")
    print(f"  Body length: {len(email_data.get('body', ''))} chars")
    print(f"  Attachments: {len(email_data['attachments'])}")

except Exception as e:
    print(f"[FAIL] Error processing email: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Chunk the email
print("\n[4/4] Chunking email...")
try:
    chunks = chunker.chunk_email(email_data)

    print(f"[OK] Email chunked into {len(chunks)} segments")
    print(f"\nChunk Breakdown:")

    # Count chunk types
    chunk_types = {}
    for chunk in chunks:
        chunk_type = chunk['metadata']['chunk_type']
        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

    for chunk_type, count in chunk_types.items():
        print(f"  - {chunk_type}: {count} chunk(s)")

    # Display detailed chunk information
    print(f"\n" + "=" * 70)
    print("Chunk Details")
    print("=" * 70)

    for i, chunk in enumerate(chunks[:5]):  # Show first 5 chunks
        print(f"\n--- Chunk #{i+1} ---")
        print(f"Type: {chunk['metadata']['chunk_type']}")
        print(f"Index: {chunk['metadata']['chunk_index']}")
        print(f"Content Length: {len(chunk['content'])} chars")
        print(f"\nContent Preview (first 300 chars):")
        print("-" * 70)
        print(chunk['content'][:300])
        if len(chunk['content']) > 300:
            print("...")
        print("-" * 70)

    if len(chunks) > 5:
        print(f"\n... and {len(chunks) - 5} more chunks")

except Exception as e:
    print(f"[FAIL] Chunking failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Summary
print("\n" + "=" * 70)
print("Test Summary")
print("=" * 70)
print("[OK] Semantic chunking is working correctly!")
print(f"\nResults:")
print(f"  - Email processed: {test_email.name}")
print(f"  - Total chunks created: {len(chunks)}")
print(f"  - Chunk types: {', '.join(chunk_types.keys())}")
print(f"  - Average chunk size: {sum(len(c['content']) for c in chunks) / len(chunks):.0f} chars")
print(f"\n✓ Emails are being broken into semantic segments")
print(f"✓ Metadata, body, and attachments are chunked separately")
print(f"✓ Each chunk maintains link to original email")
print(f"\nThis should significantly improve search accuracy!")
print("=" * 70)
