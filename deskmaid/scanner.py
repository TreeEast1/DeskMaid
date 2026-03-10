"""Desktop file scanner - collects file and folder metadata."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class FileInfo:
    name: str
    suffix: str
    size: int
    modified: str
    path: Path
    is_dir: bool = False

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "type": "folder" if self.is_dir else "file",
        }
        if not self.is_dir:
            d["suffix"] = self.suffix
            d["size_kb"] = round(self.size / 1024, 1)
            d["modified"] = self.modified
        return d


@dataclass
class ScanResult:
    files: list[FileInfo] = field(default_factory=list)
    folders: list[FileInfo] = field(default_factory=list)


def scan_desktop(desktop: Path) -> ScanResult:
    if not desktop.exists():
        return ScanResult()

    result = ScanResult()

    for item in desktop.iterdir():
        # Skip hidden files/folders
        if item.name.startswith("."):
            continue

        # Skip Office temp files
        if item.name.startswith("~$"):
            continue

        if item.is_dir():
            result.folders.append(FileInfo(
                name=item.name,
                suffix="",
                size=0,
                modified=datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                path=item,
                is_dir=True,
            ))
        else:
            stat = item.stat()
            result.files.append(FileInfo(
                name=item.name,
                suffix=item.suffix.lower(),
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                path=item,
            ))

    result.files.sort(key=lambda f: f.name)
    result.folders.sort(key=lambda f: f.name)
    return result
