import asyncio
import itertools
import logging
from pathlib import Path
from typing import Optional

from enex2notion.enex_parser import count_notes, iter_notes
from enex2notion.enex_types import EvernoteNote
from enex2notion.enex_uploader import upload_note
from enex2notion.enex_uploader_modes import get_notebook_page
from enex2notion.note_parser.note import parse_note
from enex2notion.utils_exceptions import NoteUploadFailException
from enex2notion.utils_static import Rules

logger = logging.getLogger(__name__)

# Maximum concurrent note uploads
MAX_CONCURRENT_NOTES = 3

class DoneFile(object):
    def __init__(self, path: Path):
        self.path = path

        try:
            with open(path, "r") as f:
                self.done_hashes = {line.strip() for line in f}
        except FileNotFoundError:
            self.done_hashes = set()

    def __contains__(self, note_hash):
        return note_hash in self.done_hashes

    def add(self, note_hash):
        self.done_hashes.add(note_hash)

        with open(self.path, "a") as f:
            f.write(f"{note_hash}\n")


class EnexUploader(object):
    def __init__(self, import_root, mode: str, done_file: Optional[Path], rules: Rules):
        self.import_root = import_root
        self.mode = mode

        self.rules = rules

        self.done_hashes = DoneFile(done_file) if done_file else set()

        self.notebook_root = None
        self.notebook_notes_count = None

    def upload_notebook(self, enex_file: Path):
        logger.info(f"Processing notebook '{enex_file.stem}'...")

        try:
            self.notebook_root = self._get_notebook_root(enex_file.stem)
        except NoteUploadFailException:
            if not self.rules.skip_failed:
                raise
            return

        self.notebook_notes_count = count_notes(enex_file)

        logger.debug(
            f"'{enex_file.stem}' notebook contains {self.notebook_notes_count} note(s)"
        )

        # Use async processing for concurrent note uploads
        asyncio.run(self._upload_notes_concurrent(enex_file))

    async def _upload_notes_concurrent(self, enex_file: Path):
        """Upload notes concurrently using async semaphore for rate limiting."""
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_NOTES)
        
        # Collect all notes first so we can process them concurrently
        notes_to_upload = []
        for note_idx, note in enumerate(iter_notes(enex_file), 1):
            if note.note_hash not in self.done_hashes:
                notes_to_upload.append((note, note_idx))
            else:
                logger.debug(f"Skipping note '{note.title}' (already uploaded)")
        
        if not notes_to_upload:
            logger.info("All notes already uploaded, skipping notebook")
            return
        
        logger.info(f"Uploading {len(notes_to_upload)} notes concurrently (max {MAX_CONCURRENT_NOTES} at once)")
        
        # Create async tasks for each note
        tasks = []
        for note, note_idx in notes_to_upload:
            task = asyncio.create_task(self._upload_note_async(semaphore, note, note_idx))
            tasks.append(task)
        
        # Execute all note uploads concurrently
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check for any exceptions that weren't handled
            failed_count = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception) and not self.rules.skip_failed:
                    failed_count += 1
                    logger.error(f"Unhandled error in note {i+1}: {result}")
            
            if failed_count > 0 and not self.rules.skip_failed:
                raise Exception(f"{failed_count} notes failed to upload")
                
        except Exception as e:
            logger.error(f"Error during concurrent note upload: {e}")
            if not self.rules.skip_failed:
                raise

    async def _upload_note_async(self, semaphore: asyncio.Semaphore, note: EvernoteNote, note_idx: int):
        """Upload a single note with concurrency limiting."""
        async with semaphore:
            # Run the synchronous upload_note in a thread executor
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, self.upload_note, note, note_idx)
            except Exception as e:
                logger.error(f"Failed to upload note '{note.title}': {e}")
                if not self.rules.skip_failed:
                    raise

    def upload_note(self, note: EvernoteNote, note_idx: int):
        if note.note_hash in self.done_hashes:
            logger.debug(f"Skipping note '{note.title}' (already uploaded)")
            return

        if self.rules.tag and self.rules.tag not in note.tags:
            note.tags.append(self.rules.tag)

        logger.debug(f"Parsing note '{note.title}'")

        note_blocks = self._parse_note(note)
        if not note_blocks:
            logger.debug(f"Skipping note '{note.title}' (no blocks)")
            return

        if self.notebook_root is not None:
            logger.info(
                f"Uploading note {note_idx}"
                f" out of {self.notebook_notes_count} '{note.title}'"
            )

            try:
                self._upload_note(self.notebook_root, note, note_blocks)
            except NoteUploadFailException:
                if not self.rules.skip_failed:
                    raise
                return

            self.done_hashes.add(note.note_hash)

    def _parse_note(self, note):
        try:
            return parse_note(note, self.rules)
        except Exception as e:
            logger.error(f"Failed to parse note '{note.title}'")
            logger.debug(e, exc_info=e)
            return []

    def _get_notebook_root(self, notebook_title):
        if self.import_root is None:
            return None

        error_message = f"Failed to get notebook root for '{notebook_title}'"
        get_func = get_notebook_page if self.mode == "DB" else get_notebook_page

        return self._attempt_upload(
            get_func, error_message, self.import_root, notebook_title
        )

    def _upload_note(self, notebook_root, note, note_blocks):
        self._attempt_upload(
            upload_note,
            f"Failed to upload note '{note.title}' to Notion",
            notebook_root,
            note,
            note_blocks,
            self.rules.keep_failed,
        )

    def _attempt_upload(self, upload_func, error_message, *args, **kwargs):
        for attempt in itertools.count(1):
            try:
                return upload_func(*args, **kwargs)
            except NoteUploadFailException as e:
                logger.debug(f"Upload error: {e}", exc_info=e)

                if attempt == self.rules.retry:
                    logger.error(f"{error_message}!")
                    raise

                logger.warning(f"{error_message}! Retrying...")
