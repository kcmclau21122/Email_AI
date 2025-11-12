"""
Test script to verify that email content from .eml files is being extracted properly.
"""

import sys
from pathlib import Path

print("=" * 60)
print("Email Content Extraction Test")
print("=" * 60)

# Test email processing
print("\n[1/3] Testing email processor...")
try:
    from email_processor import EmailProcessor
    print("[OK] EmailProcessor imported")
except ImportError as e:
    print(f"[FAIL] Failed to import: {e}")
    sys.exit(1)

# Test with a sample email
print("\n[2/3] Processing sample emails...")
email_dir = input("Enter path to email directory: ").strip()

if not email_dir:
    email_dir = "g:/emails/mclaurinkevinc@protonmail.com/mail_20251112_132400"

email_path = Path(email_dir)
if not email_path.exists():
    print(f"[FAIL] Directory not found: {email_dir}")
    sys.exit(1)

processor = EmailProcessor(str(email_path), filter_config_path=None)  # Disable filters for testing
email_files = processor.get_email_files()

if not email_files:
    print(f"[FAIL] No email files found in {email_dir}")
    sys.exit(1)

print(f"[OK] Found {len(email_files)} email files")

# Test first email
print("\n[3/3] Testing first email extraction...")
test_email = email_files[0]
print(f"Testing: {test_email.name}")

email_data = processor.parse_email(test_email, apply_filters=False)

if not email_data:
    print("[FAIL] Failed to parse email")
    sys.exit(1)

print(f"[OK] Email parsed successfully")
print(f"\nEmail Details:")
print(f"  Subject: {email_data['subject']}")
print(f"  From: {email_data['from']}")
print(f"  Date: {email_data['date']}")
print(f"  Attachments: {len(email_data['attachments'])}")

# Check body content
body = email_data.get('body', '')
print(f"\n  Body Length: {len(body)} characters")

if len(body) > 0:
    print(f"  Body Preview (first 200 chars):")
    print(f"  {body[:200]}...")
else:
    print("  [WARN] Body is empty!")

# Get full text content
full_text = processor.get_all_text_content(email_data)
print(f"\n  Full Text Length: {len(full_text)} characters")
print(f"  Full Text Preview (first 500 chars):")
print("  " + "-" * 60)
print(full_text[:500])
print("  " + "-" * 60)

# Check if body is in full text
if body and body in full_text:
    print("\n[OK] Body content IS included in full text!")
else:
    print("\n[WARN] Body content might not be properly included")

# Summary
print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)

if len(body) > 100:
    print("[OK] Email body is being extracted")
    print(f"[OK] Body length: {len(body)} characters")
else:
    print(f"[WARN] Email body seems short or empty ({len(body)} chars)")
    print("      This could mean:")
    print("      1. The email actually has no body content")
    print("      2. The body is HTML-only (check if text/html exists)")
    print("      3. There's an encoding issue")

if len(full_text) > len(body):
    print("[OK] Full text includes more than just body (metadata + body + attachments)")
else:
    print("[WARN] Full text might not be combining all components")

print("\n" + "=" * 60)
