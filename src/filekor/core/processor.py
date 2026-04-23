"""Parallel processing engine for core module - directory batch operations."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional

from filekor.constants import FILEKOR_DIR, KOR_EXTENSION
from filekor.core.models.process_result import ProcessResult, SUPPORTED_EXTENSIONS
from filekor.adapters.exiftool import PyExifToolAdapter
from filekor.sidecar import Sidecar, Content
from filekor.core.labels import LabelsConfig, LLMConfig, suggest_labels
from filekor.core.summary import generate_summary
from filekor.sidecar import Sidecar, Content, FileSummary


class DirectoryProcessor:
    """Handles parallel processing of directories with ThreadPoolExecutor."""

    def __init__(
        self,
        workers: int = 4,
        output_dir: Optional[Path] = None,
        llm_config: Optional[LLMConfig] = None,
        labels_config: Optional[LabelsConfig] = None,
        write_kor: bool = True,
        add_labels: bool = False,
        add_summary: bool = False,
        summary_length: str = "both",
    ):
        """Initialize DirectoryProcessor.

        Args:
            workers: Number of parallel workers.
            output_dir: Output directory for .kor files (default: .filekor/)
            llm_config: LLM configuration for label extraction.
            labels_config: Labels configuration for taxonomy.
            write_kor: Write individual .kor files to disk. When False, process only (for memory-only merge mode).
            add_labels: Generate labels via LLM.
            add_summary: Generate summaries via LLM.
            summary_length: Summary length when add_summary is used ("short", "long", "both").
        """
        self.workers = workers
        self.output_dir = output_dir
        self.llm_config = llm_config or LLMConfig.load()
        self.labels_config = labels_config or LabelsConfig.load()
        self.adapter = PyExifToolAdapter()
        self.write_kor = write_kor
        self.add_labels = add_labels
        self.add_summary = add_summary
        self.summary_length = summary_length

    def get_output_path(self, input_path: Path) -> Path:
        """Get output path for a processed file.

        Args:
            input_path: Original file path.

        Returns:
            Path for the .kor output file.
        """
        ext = input_path.suffix.lstrip(".").lower()
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            return self.output_dir / f"{input_path.stem}.{ext}{KOR_EXTENSION}"
        else:
            filekor_dir = input_path.parent / FILEKOR_DIR
            filekor_dir.mkdir(parents=True, exist_ok=True)
            return filekor_dir / f"{input_path.stem}.{ext}{KOR_EXTENSION}"

    def process_file(self, file_path: Path) -> ProcessResult:
        """Process a single file.

        Args:
            file_path: Path to the file to process.

        Returns:
            ProcessResult with success status and output path.
        """
        try:
            # Extract metadata (exiftool)
            metadata = None
            if self.adapter.is_available():
                try:
                    metadata = self.adapter.extract_metadata(str(file_path))
                except Exception:
                    pass

            # Extract text content
            content_obj = None
            text_content = None
            try:
                from filekor.cli import extract_text

                text, word_count, page_count = extract_text(str(file_path))
                text_content = text
                content_obj = Content(
                    language="en",
                    word_count=word_count,
                    page_count=page_count,
                )
            except Exception:
                pass

            # Create sidecar
            sidecar = Sidecar.create(
                str(file_path),
                metadata=metadata,
                content=content_obj,
            )

            # Add labels if enabled and LLM is configured
            labels = None
            if self.add_labels and self.llm_config.enabled and self.llm_config.api_key and text_content:
                try:
                    labels = suggest_labels(
                        content=text_content,
                        config=self.labels_config,
                        llm_config=self.llm_config,
                    )
                    sidecar.update_labels(labels)
                except Exception:
                    pass

            # Add summaries if enabled
            if self.add_summary and self.llm_config.enabled and self.llm_config.api_key and text_content:
                try:
                    result = generate_summary(
                        content=text_content,
                        length=self.summary_length,
                        llm_config=self.llm_config,
                    )
                    sidecar.summary = FileSummary(
                        short=result.short,
                        long=result.long,
                    )
                except Exception:
                    pass

            # Write output (skip in memory-only merge mode)
            if self.write_kor:
                output_path = self.get_output_path(file_path)
                output_path.write_text(sidecar.to_yaml())
            else:
                output_path = None

            return ProcessResult(
                file_path=file_path,
                success=True,
                output_path=output_path,
                labels=labels,
                sidecar=sidecar,
            )

        except Exception as e:
            return ProcessResult(
                file_path=file_path,
                success=False,
                error=str(e),
            )

    def process_directory(
        self,
        directory: Path,
        recursive: bool = True,
        callback: Optional[Callable[[ProcessResult], None]] = None,
    ) -> List[ProcessResult]:
        """Process all supported files in a directory.

        Args:
            directory: Directory to process.
            recursive: Whether to process subdirectories.
            callback: Optional callback for each completed file.

        Returns:
            List of ProcessResult for each file.
        """
        pattern = "**/*" if recursive else "*"
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(directory.glob(f"{pattern}.{ext}"))

        files = [f for f in files if FILEKOR_DIR not in f.parts]

        results: List[ProcessResult] = []

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.process_file, f): f for f in files}

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                if callback:
                    callback(result)

        return results


def process_directory(
    path: str,
    workers: Optional[int] = None,
    output_dir: Optional[str] = None,
    recursive: bool = True,
    llm_config: Optional[LLMConfig] = None,
    labels_config: Optional[LabelsConfig] = None,
    callback: Optional[Callable[[ProcessResult], None]] = None,
) -> List[ProcessResult]:
    """Process a directory of files using parallel workers.

    Args:
        path: Path to directory.
        workers: Number of parallel workers (default from config).
        output_dir: Output directory for .kor files.
        recursive: Process subdirectories.
        llm_config: LLM configuration.
        labels_config: Labels configuration.
        callback: Optional callback for progress updates.

    Returns:
        List of ProcessResult for each file.
    """
    if workers is None:
        llm_cfg = llm_config or LLMConfig.load()
        workers = llm_cfg.workers

    processor = DirectoryProcessor(
        workers=workers,
        output_dir=Path(output_dir) if output_dir else None,
        llm_config=llm_config,
        labels_config=labels_config,
    )

    return processor.process_directory(
        directory=Path(path),
        recursive=recursive,
        callback=callback,
    )
