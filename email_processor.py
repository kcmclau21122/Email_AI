"""
Email processing module for extracting and processing email content and attachments.
Handles various email formats and attachment types.
Supports filtering based on sender, subject, and other criteria.
"""

import email
import os
import json
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import mimetypes

from docx import Document
import PyPDF2

from logger_config import LoggerConfig, log_function_call


logger = LoggerConfig.get_logger()


class EmailFilter:
    """Handles email filtering based on configuration."""

    def __init__(self, filter_config_path: str = "email_filters.json"):
        """
        Initialize email filter with configuration.

        Args:
            filter_config_path: Path to filter configuration JSON file
        """
        self.filter_config_path = Path(filter_config_path)
        self.config = self._load_config()
        self.stats = {
            'total_checked': 0,
            'filtered_out': 0,
            'passed': 0,
            'whitelisted': 0,
            'reasons': {}
        }
        logger.info(f"EmailFilter initialized with config: {filter_config_path}")

    def _load_config(self) -> Dict:
        """Load filter configuration from JSON file."""
        try:
            if self.filter_config_path.exists():
                with open(self.filter_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info("Filter configuration loaded successfully")
                return config
            else:
                logger.warning(f"Filter config not found: {self.filter_config_path}, using no filters")
                return {'filters': {}, 'whitelist': {'enabled': False}}
        except Exception as e:
            logger.error(f"Error loading filter config: {str(e)}")
            return {'filters': {}, 'whitelist': {'enabled': False}}

    @log_function_call
    def should_process_email(self, metadata: Dict) -> Tuple[bool, str]:
        """
        Determine if an email should be processed based on filters.

        Args:
            metadata: Email metadata from .metadata.json file

        Returns:
            Tuple of (should_process: bool, reason: str)
        """
        self.stats['total_checked'] += 1

        # Extract payload
        payload = metadata.get('Payload', {})
        sender = payload.get('Sender', {})
        sender_address = sender.get('Address', '').lower()
        sender_name = sender.get('Name', '')
        subject = payload.get('Subject', '')
        label_ids = payload.get('LabelIDs', [])
        num_attachments = payload.get('NumAttachments', 0)
        email_time = payload.get('Time', 0)

        # Check whitelist first (overrides all filters)
        whitelist = self.config.get('whitelist', {})
        if whitelist.get('enabled', False):
            if self._check_whitelist(sender_address, sender_name, whitelist):
                self.stats['whitelisted'] += 1
                self.stats['passed'] += 1
                return True, "Whitelisted"

        filters = self.config.get('filters', {})

        # Check ignore_senders (email addresses and domains)
        ignore_senders = filters.get('ignore_senders', {})
        if ignore_senders.get('enabled', False):
            addresses = [addr.lower() for addr in ignore_senders.get('addresses', [])]
            domains = [domain.lower() for domain in ignore_senders.get('domains', [])]

            if sender_address in addresses:
                reason = f"Sender address blocked: {sender_address}"
                self._record_filtered(reason)
                return False, reason

            sender_domain = sender_address.split('@')[-1] if '@' in sender_address else ''
            if sender_domain in domains:
                reason = f"Sender domain blocked: {sender_domain}"
                self._record_filtered(reason)
                return False, reason

        # Check ignore_sender_names
        ignore_names = filters.get('ignore_sender_names', {})
        if ignore_names.get('enabled', False):
            names = [name.lower() for name in ignore_names.get('names', [])]
            sender_name_lower = sender_name.lower()

            for blocked_name in names:
                if blocked_name in sender_name_lower:
                    reason = f"Sender name blocked: {sender_name}"
                    self._record_filtered(reason)
                    return False, reason

        # Check ignore_subjects
        ignore_subjects = filters.get('ignore_subjects', {})
        if ignore_subjects.get('enabled', False):
            keywords = [kw.lower() for kw in ignore_subjects.get('keywords', [])]
            subject_lower = subject.lower()

            for keyword in keywords:
                if keyword in subject_lower:
                    reason = f"Subject keyword blocked: {keyword}"
                    self._record_filtered(reason)
                    return False, reason

        # Check ignore_label_ids
        ignore_labels = filters.get('ignore_label_ids', {})
        if ignore_labels.get('enabled', False):
            blocked_labels = ignore_labels.get('label_ids', [])

            for label in label_ids:
                if str(label) in blocked_labels:
                    reason = f"Label ID blocked: {label}"
                    self._record_filtered(reason)
                    return False, reason

        # Check require_attachments
        require_attachments = filters.get('require_attachments', {})
        if require_attachments.get('enabled', False):
            if num_attachments == 0:
                reason = "No attachments (required)"
                self._record_filtered(reason)
                return False, reason

        # Check date_range
        date_range = filters.get('date_range', {})
        if date_range.get('enabled', False):
            start_date = date_range.get('start_date')
            end_date = date_range.get('end_date')

            if start_date and email_time < start_date:
                reason = f"Email too old: {email_time}"
                self._record_filtered(reason)
                return False, reason

            if end_date and email_time > end_date:
                reason = f"Email too new: {email_time}"
                self._record_filtered(reason)
                return False, reason

        # Passed all filters
        self.stats['passed'] += 1
        return True, "Passed all filters"

    def _check_whitelist(self, sender_address: str, sender_name: str, whitelist: Dict) -> bool:
        """Check if sender is whitelisted."""
        addresses = [addr.lower() for addr in whitelist.get('sender_addresses', [])]
        domains = [domain.lower() for domain in whitelist.get('sender_domains', [])]

        if sender_address in addresses:
            return True

        sender_domain = sender_address.split('@')[-1] if '@' in sender_address else ''
        if sender_domain in domains:
            return True

        return False

    def _record_filtered(self, reason: str):
        """Record filtering statistics."""
        self.stats['filtered_out'] += 1
        self.stats['reasons'][reason] = self.stats['reasons'].get(reason, 0) + 1

    @log_function_call
    def get_statistics(self) -> Dict:
        """Get filtering statistics."""
        return self.stats.copy()

    @log_function_call
    def reset_statistics(self):
        """Reset filtering statistics."""
        self.stats = {
            'total_checked': 0,
            'filtered_out': 0,
            'passed': 0,
            'whitelisted': 0,
            'reasons': {}
        }
        logger.info("Filter statistics reset")


class EmailProcessor:
    """Processes emails and extracts content from emails and attachments."""

    def __init__(self, email_directory: str, filter_config_path: Optional[str] = "email_filters.json"):
        """
        Initialize the email processor.

        Args:
            email_directory: Path to directory containing email files
            filter_config_path: Path to filter configuration file (None to disable filtering)
        """
        self.email_directory = Path(email_directory)
        self.email_filter = EmailFilter(filter_config_path) if filter_config_path else None
        logger.info(f"EmailProcessor initialized with directory: {email_directory}")
        if self.email_filter:
            logger.info("Email filtering enabled")

    def _read_metadata(self, email_path: Path) -> Optional[Dict]:
        """
        Read ProtonMail metadata.json file for an email.

        Args:
            email_path: Path to the .eml file

        Returns:
            Metadata dictionary or None if not found
        """
        try:
            # Look for metadata.json with same base name
            metadata_path = email_path.with_suffix('.metadata.json')

            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                logger.debug(f"Read metadata for: {email_path.name}")
                return metadata
            else:
                logger.debug(f"No metadata file found for: {email_path.name}")
                return None

        except Exception as e:
            logger.error(f"Error reading metadata for {email_path}: {str(e)}")
            return None

    @log_function_call
    def get_email_files(self) -> List[Path]:
        """
        Get all email files from the specified directory.

        Returns:
            List of Path objects for email files
        """
        email_extensions = ['.eml', '.msg', '.mbox']
        email_files = []

        if not self.email_directory.exists():
            logger.error(f"Email directory does not exist: {self.email_directory}")
            return email_files

        for ext in email_extensions:
            email_files.extend(self.email_directory.rglob(f"*{ext}"))

        logger.info(f"Found {len(email_files)} email files")
        return email_files

    @log_function_call
    def parse_email(self, email_path: Path, apply_filters: bool = True) -> Optional[Dict]:
        """
        Parse an email file and extract metadata and content.

        Args:
            email_path: Path to the email file
            apply_filters: Whether to apply email filters (default: True)

        Returns:
            Dictionary containing email data or None if parsing fails or filtered out
        """
        try:
            # Read ProtonMail metadata if available
            pm_metadata = self._read_metadata(email_path)

            # Apply filters if enabled
            if apply_filters and self.email_filter and pm_metadata:
                should_process, reason = self.email_filter.should_process_email(pm_metadata)
                if not should_process:
                    logger.info(f"Email filtered out: {email_path.name} - Reason: {reason}")
                    return None

            # Parse email content
            with open(email_path, 'rb') as f:
                msg = BytesParser(policy=policy.default).parse(f)

            # Use ProtonMail metadata if available, otherwise use email headers
            if pm_metadata and 'Payload' in pm_metadata:
                payload = pm_metadata['Payload']
                sender = payload.get('Sender', {})
                to_list = payload.get('ToList', [])

                email_data = {
                    'subject': payload.get('Subject', 'No Subject'),
                    'from': f"{sender.get('Name', '')} <{sender.get('Address', 'Unknown')}>",
                    'to': ', '.join([f"{t.get('Name', '')} <{t.get('Address', '')}>" for t in to_list]),
                    'date': payload.get('Time', 'Unknown'),
                    'body': self._extract_body(msg),
                    'attachments': [],
                    'file_path': str(email_path),
                    'metadata': pm_metadata
                }
            else:
                # Fallback to email headers
                email_data = {
                    'subject': msg.get('subject', 'No Subject'),
                    'from': msg.get('from', 'Unknown'),
                    'to': msg.get('to', 'Unknown'),
                    'date': msg.get('date', 'Unknown'),
                    'body': self._extract_body(msg),
                    'attachments': [],
                    'file_path': str(email_path),
                    'metadata': None
                }

            # Process attachments
            for part in msg.walk():
                if part.get_content_disposition() == 'attachment':
                    attachment_data = self._process_attachment(part)
                    if attachment_data:
                        email_data['attachments'].append(attachment_data)

            logger.debug(f"Successfully parsed email: {email_path.name}")
            return email_data

        except Exception as e:
            logger.error(f"Failed to parse email {email_path}: {str(e)}")
            return None

    def _extract_body(self, msg) -> str:
        """
        Extract the body text from an email message.

        Args:
            msg: Email message object

        Returns:
            Email body text
        """
        body = ""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))

                    # Skip attachments
                    if 'attachment' in content_disposition:
                        continue

                    if content_type == 'text/plain':
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    elif content_type == 'text/html' and not body:
                        # Fallback to HTML if no plain text
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

        except Exception as e:
            logger.error(f"Error extracting email body: {str(e)}")

        return body

    def _process_attachment(self, part) -> Optional[Dict]:
        """
        Process an email attachment and extract text content.

        Args:
            part: Email message part containing attachment

        Returns:
            Dictionary with attachment metadata and content
        """
        try:
            filename = part.get_filename()
            if not filename:
                return None

            content = part.get_payload(decode=True)
            file_ext = Path(filename).suffix.lower()

            attachment_data = {
                'filename': filename,
                'content_type': part.get_content_type(),
                'text_content': ''
            }

            # Extract text based on file type
            if file_ext == '.pdf':
                attachment_data['text_content'] = self._extract_pdf_text(content)
            elif file_ext in ['.docx', '.doc']:
                attachment_data['text_content'] = self._extract_docx_text(content)
            elif file_ext in ['.txt', '.text']:
                attachment_data['text_content'] = content.decode('utf-8', errors='ignore')
            else:
                logger.debug(f"Unsupported attachment type: {file_ext}")

            return attachment_data

        except Exception as e:
            logger.error(f"Error processing attachment: {str(e)}")
            return None

    def _extract_pdf_text(self, content: bytes) -> str:
        """
        Extract text from PDF content.

        Args:
            content: PDF file content as bytes

        Returns:
            Extracted text
        """
        try:
            import io
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            return ""

    def _extract_docx_text(self, content: bytes) -> str:
        """
        Extract text from DOCX content.

        Args:
            content: DOCX file content as bytes

        Returns:
            Extracted text
        """
        try:
            import io
            docx_file = io.BytesIO(content)
            doc = Document(docx_file)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except Exception as e:
            logger.error(f"Error extracting DOCX text: {str(e)}")
            return ""

    @log_function_call
    def process_all_emails(self) -> List[Dict]:
        """
        Process all emails in the directory.

        Returns:
            List of processed email data dictionaries
        """
        email_files = self.get_email_files()
        processed_emails = []

        for email_file in email_files:
            email_data = self.parse_email(email_file)
            if email_data:
                processed_emails.append(email_data)

        logger.info(f"Successfully processed {len(processed_emails)} emails")
        return processed_emails

    @log_function_call
    def get_all_text_content(self, email_data: Dict) -> str:
        """
        Combine email body and attachment text into a single string.

        Args:
            email_data: Processed email data dictionary

        Returns:
            Combined text content
        """
        text_parts = []

        # Add email metadata
        text_parts.append(f"Subject: {email_data['subject']}")
        text_parts.append(f"From: {email_data['from']}")
        text_parts.append(f"To: {email_data['to']}")
        text_parts.append(f"Date: {email_data['date']}")
        text_parts.append("\nBody:")
        text_parts.append(email_data['body'])

        # Add attachment content
        if email_data['attachments']:
            text_parts.append("\n--- Attachments ---")
            for attachment in email_data['attachments']:
                text_parts.append(f"\nAttachment: {attachment['filename']}")
                if attachment['text_content']:
                    text_parts.append(attachment['text_content'])

        return "\n".join(text_parts)

    @log_function_call
    def get_filter_statistics(self) -> Optional[Dict]:
        """
        Get email filtering statistics.

        Returns:
            Dictionary with filter statistics or None if filtering is disabled
        """
        if self.email_filter:
            return self.email_filter.get_statistics()
        return None

    @log_function_call
    def reset_filter_statistics(self):
        """Reset email filtering statistics."""
        if self.email_filter:
            self.email_filter.reset_statistics()
