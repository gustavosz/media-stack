#!/usr/bin/env python3
"""
Calibre-Web Automated Book Importer & Kindle Delivery Pipeline.
Structured with Domain Value Objects, Repositories, and Application Services.
"""

from __future__ import annotations

import os
import re
import shutil
import smtplib
import sqlite3
import ssl
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree


def log(msg: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [AutoImport] {msg}", flush=True)


# ------------------------------------------------------------------------------
# Value Objects
# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class SmtpCredentials:
    server: str
    port: int
    login: str
    password: str
    sender: str
    recipient_kindle: Optional[str]

    @property
    def can_send_to_kindle(self) -> bool:
        return bool(self.server and self.recipient_kindle)


@dataclass(frozen=True)
class ImportedBook:
    book_id: Optional[str]
    title: str
    original_path: str
    epub_path: Optional[str] = None
    pdf_path: Optional[str] = None

    @property
    def preferred_kindle_path(self) -> str:
        if self.epub_path and os.path.exists(self.epub_path):
            return self.epub_path
        return self.original_path


# ------------------------------------------------------------------------------
# Repositories & Gateways
# ------------------------------------------------------------------------------
class CalibreSettingsRepository:
    """Reads decrypted SMTP and Kindle user settings from Calibre-Web's SQLite DB."""

    def __init__(
        self, db_path: str = "/config/app.db", key_path: str = "/config/.key"
    ) -> None:
        self._db_path = db_path
        self._key_path = key_path

    def get_smtp_credentials(self) -> Optional[SmtpCredentials]:
        try:
            from cryptography.fernet import Fernet

            if not os.path.exists(self._db_path) or not os.path.exists(self._key_path):
                return None
            with open(self._key_path, "rb") as f:
                key = f.read().strip()
            cipher = Fernet(key)

            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT mail_server, mail_port, mail_login, mail_password_e, mail_from "
                "FROM settings WHERE id = 1"
            )
            row = cursor.fetchone()
            if not row or not row[0] or not row[3]:
                conn.close()
                return None

            server, port, login, pw_enc, mail_from = row
            password = cipher.decrypt(pw_enc.encode()).decode()

            cursor.execute("SELECT kindle_mail FROM user WHERE name = 'admin'")
            user_row = cursor.fetchone()
            kindle_mail = user_row[0] if user_row and user_row[0] else None
            conn.close()

            return SmtpCredentials(
                server=server,
                port=int(port),
                login=login,
                password=password,
                sender=mail_from or login,
                recipient_kindle=kindle_mail,
            )
        except Exception as e:
            log(f"Error reading SMTP configuration: {e}")
            return None


class CalibreLibraryRepository:
    """Interacts with the physical Calibre database via calibredb and ebook-convert."""

    def __init__(self, library_dir: str = "/books") -> None:
        self._library_dir = library_dir

    def add_book(self, filepath: str) -> Optional[ImportedBook]:
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()

        log(f"Importing {filename} into Calibre library...")
        res = subprocess.run(
            ["calibredb", "add", filepath, f"--library-path={self._library_dir}"],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            log(f"calibredb add failed: {res.stderr.strip()}")
            return None

        match = re.search(r"Added book ids?:\s*(\d+)", res.stdout)
        book_id = match.group(1) if match else None
        log(f"Import successful! Calibre book ID: {book_id}")

        title = filename
        epub_path: Optional[str] = None
        pdf_path: Optional[str] = None

        if book_id:
            title = self._fetch_title(book_id, default=filename)
            epub_path, pdf_path = self._fetch_formats(book_id)

            if ext == ".pdf" and not epub_path:
                epub_path = self._convert_pdf_to_epub(book_id, filepath)

            if epub_path and os.path.exists(epub_path):
                self._optimize_epub_cover(book_id, epub_path)

        return ImportedBook(
            book_id=book_id,
            title=title,
            original_path=filepath,
            epub_path=epub_path,
            pdf_path=pdf_path,
        )

    def _fetch_title(self, book_id: str, default: str) -> str:
        res = subprocess.run(
            [
                "calibredb",
                "show_metadata",
                book_id,
                f"--library-path={self._library_dir}",
            ],
            capture_output=True,
            text=True,
        )
        match = re.search(r"Title\s*:\s*(.+)", res.stdout)
        return match.group(1).strip() if match else default

    def _fetch_formats(self, book_id: str) -> tuple[Optional[str], Optional[str]]:
        epub_path: Optional[str] = None
        pdf_path: Optional[str] = None
        res = subprocess.run(
            [
                "calibredb",
                "list",
                f"--library-path={self._library_dir}",
                f"--search=id:{book_id}",
                "--fields=formats",
            ],
            capture_output=True,
            text=True,
        )
        for line in res.stdout.splitlines():
            for fmt_file in re.findall(r"(/books/[^,\n\]]+)", line):
                if fmt_file.endswith(".epub"):
                    epub_path = fmt_file
                elif fmt_file.endswith(".pdf"):
                    pdf_path = fmt_file
        return epub_path, pdf_path

    def _convert_pdf_to_epub(self, book_id: str, filepath: str) -> Optional[str]:
        log("Generating EPUB version from PDF with ebook-convert...")
        temp_epub = f"/tmp/{book_id}_converted.epub"
        res = subprocess.run(
            ["ebook-convert", filepath, temp_epub], capture_output=True, text=True
        )
        if res.returncode == 0 and os.path.exists(temp_epub):
            subprocess.run(
                [
                    "calibredb",
                    "add_format",
                    f"--library-path={self._library_dir}",
                    book_id,
                    temp_epub,
                ],
                capture_output=True,
            )
            log("EPUB version created and attached successfully!")
            return temp_epub
        return None

    def _optimize_epub_cover(self, book_id: str, epub_path: str) -> None:
        cover_path = os.path.join(os.path.dirname(epub_path), "cover.jpg")
        temp_fixed = f"/tmp/{book_id}_fixed.epub"
        cmd = ["ebook-convert", epub_path, temp_fixed]
        if os.path.exists(cover_path):
            cmd.append(f"--cover={cover_path}")
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode == 0 and os.path.exists(temp_fixed):
            shutil.move(temp_fixed, epub_path)
            log("EPUB cover semantics optimized for Kindle.")


class KindleMailerService:
    """Dispatches eBooks to Amazon Kindle via SMTP."""

    def send(self, creds: SmtpCredentials, file_path: str, title: str) -> bool:
        if not creds.can_send_to_kindle or not creds.recipient_kindle:
            log("No Kindle email configured. Skipping automatic Kindle delivery.")
            return False

        try:
            log(
                f"Sending '{title}' ({os.path.basename(file_path)}) to Kindle: {creds.recipient_kindle}..."
            )
            msg = EmailMessage()
            msg["Subject"] = title
            msg["From"] = creds.sender
            msg["To"] = creds.recipient_kindle
            msg.set_content(f"Libro importado automáticamente: {title}")

            ext = os.path.splitext(file_path)[1].lower()
            subtype = (
                "epub+zip"
                if ext == ".epub"
                else "pdf"
                if ext == ".pdf"
                else "octet-stream"
            )

            with open(file_path, "rb") as f:
                data = f.read()

            msg.add_attachment(
                data,
                maintype="application",
                subtype=subtype,
                filename=os.path.basename(file_path),
            )

            context = ssl.create_default_context()
            with smtplib.SMTP(creds.server, creds.port, timeout=60) as smtp:
                smtp.starttls(context=context)
                smtp.login(creds.login, creds.password)
                smtp.send_message(msg)

            log("Successfully dispatched to Kindle!")
            return True
        except Exception as e:
            log(f"Failed to send to Kindle: {e}")
            return False


class ChaptarrGateway:
    """Notifies Chaptarr to rescan book folders after import."""

    def __init__(self, config_xml_path: str = "/chaptarr-config/config.xml") -> None:
        self._config_xml_path = Path(config_xml_path)

    def _resolve_api_key(self) -> Optional[str]:
        env_key = os.getenv("CHAPTARR_API_KEY")
        if env_key:
            return env_key
        if self._config_xml_path.is_file():
            try:
                tree = ElementTree.parse(self._config_xml_path)
                elem = tree.getroot().find("ApiKey")
                if elem is not None and elem.text:
                    return elem.text.strip()
            except Exception:
                pass
        return None

    def trigger_rescan(self) -> None:
        api_key = self._resolve_api_key()
        if not api_key:
            return
        try:
            cmd = [
                "curl",
                "-s",
                "-m",
                "10",
                "http://chaptarr:8789/api/v1/command",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-H",
                f"X-Api-Key: {api_key}",
                "-d",
                '{"name": "RescanFolders"}',
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


# ------------------------------------------------------------------------------
# Application Use Case
# ------------------------------------------------------------------------------
class AutoImportBooksUseCase:
    VALID_EXTENSIONS = {".epub", ".pdf", ".mobi", ".azw3", ".cbr", ".cbz"}
    IGNORE_EXTENSIONS = {".crdownload", ".part", ".tmp", ".download"}

    def __init__(
        self,
        import_dir: str = "/import_books",
        failed_dir: str = "/import_books/failed",
    ) -> None:
        self._import_dir = import_dir
        self._failed_dir = failed_dir
        self._settings_repo = CalibreSettingsRepository()
        self._library_repo = CalibreLibraryRepository()
        self._mailer = KindleMailerService()
        self._chaptarr = ChaptarrGateway()

    def execute(self) -> None:
        if not os.path.exists(self._import_dir):
            return

        candidate_files = self._scan_import_directory()
        if not candidate_files:
            return

        smtp_creds = self._settings_repo.get_smtp_credentials()
        for filepath in candidate_files:
            self._process_single_file(filepath, smtp_creds)

    def _scan_import_directory(self) -> List[str]:
        results: List[str] = []
        for fname in os.listdir(self._import_dir):
            full_path = os.path.join(self._import_dir, fname)
            if not os.path.isfile(full_path) or fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in self.IGNORE_EXTENSIONS or ext not in self.VALID_EXTENSIONS:
                continue
            results.append(full_path)
        return results

    @staticmethod
    def _is_file_stable(filepath: str) -> bool:
        try:
            s1 = os.path.getsize(filepath)
            time.sleep(2)
            s2 = os.path.getsize(filepath)
            return s1 == s2 and s1 > 0
        except OSError:
            return False

    def _process_single_file(
        self, filepath: str, smtp_creds: Optional[SmtpCredentials]
    ) -> None:
        filename = os.path.basename(filepath)
        log(f"Detected incoming book: {filename}")

        if not self._is_file_stable(filepath):
            log(f"File {filename} is still writing/unstable. Skipping until next run.")
            return

        imported = self._library_repo.add_book(filepath)
        if not imported:
            os.makedirs(self._failed_dir, exist_ok=True)
            shutil.move(filepath, os.path.join(self._failed_dir, filename))
            return

        if smtp_creds:
            self._mailer.send(
                smtp_creds, imported.preferred_kindle_path, imported.title
            )

        try:
            os.remove(filepath)
            log(f"Cleaned up {filename} from import folder.")
        except Exception as e:
            log(f"Warning: could not delete {filename}: {e}")

        self._chaptarr.trigger_rescan()


if __name__ == "__main__":
    AutoImportBooksUseCase().execute()
