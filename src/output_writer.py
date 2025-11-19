"""
Thread-safe streaming CSV writer with crash recovery.
"""
import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class StreamingWriter:
    """Thread-safe CSV writer with append-mode and crash recovery."""

    def __init__(self, output_path: str, columns: List[str]):
        """
        Initialize streaming writer.

        Args:
            output_path: Path to output CSV file
            columns: List of column names
        """
        self.output_path = Path(output_path)
        self.columns = columns
        self.write_lock = Lock()

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Track completed domains
        self.completed_domains = self._load_completed_domains()

        # Initialize file if it doesn't exist
        if not self.output_path.exists():
            self._write_header()

        logger.info(f"StreamingWriter initialized. {len(self.completed_domains)} domains already processed.")

    def _load_completed_domains(self) -> Set[str]:
        """Load set of domains that have been completed."""
        completed = set()

        if not self.output_path.exists():
            return completed

        try:
            with open(self.output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    domain = row.get('domain')
                    finished_at = row.get('finished_at')

                    # Only count as completed if it has a finished_at timestamp
                    if domain and finished_at:
                        completed.add(domain)

            logger.info(f"Loaded {len(completed)} completed domains from existing output")

        except Exception as e:
            logger.warning(f"Error loading completed domains: {e}")

        return completed

    def _write_header(self):
        """Write CSV header."""
        with open(self.output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.columns)
            writer.writeheader()
            f.flush()
            os.fsync(f.fileno())

    def is_completed(self, domain: str) -> bool:
        """Check if domain has already been processed."""
        return domain in self.completed_domains

    def write_row(self, row_data: Dict):
        """
        Write a single row to the CSV file (thread-safe).

        Args:
            row_data: Dictionary with row data
        """
        with self.write_lock:
            try:
                # Add timestamps
                domain = row_data['domain']

                if 'finished_at' not in row_data or not row_data['finished_at']:
                    row_data['finished_at'] = datetime.utcnow().isoformat()

                # Ensure all columns are present
                full_row = {col: row_data.get(col, '') for col in self.columns}

                # Append to file
                file_exists = self.output_path.exists()
                with open(self.output_path, 'a', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self.columns)

                    # Write header if file is empty
                    if not file_exists or self.output_path.stat().st_size == 0:
                        writer.writeheader()

                    writer.writerow(full_row)

                    # Flush to disk immediately
                    f.flush()
                    os.fsync(f.fileno())

                # Mark as completed
                self.completed_domains.add(domain)

                logger.debug(f"Wrote result for {domain}")

            except Exception as e:
                logger.error(f"Error writing row for {domain}: {e}")

    def write_error(self, domain: str, error: str):
        """Write an error result for a domain."""
        row_data = {
            'domain': domain,
            'label': 'Error',
            'confidence': 0.0,
            'text_score': None,
            'vision_score': None,
            'reasons': '',
            'image_count': 0,
            'error': str(error)[:500],  # Truncate long errors
            'started_at': datetime.utcnow().isoformat(),
            'finished_at': datetime.utcnow().isoformat()
        }
        self.write_row(row_data)

    def get_completed_count(self) -> int:
        """Get number of completed domains."""
        return len(self.completed_domains)
