"""Parses, validates, and writes SSH configuration files."""

from __future__ import annotations

import fnmatch
import glob
import logging
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class SSHOption:
    key: str
    value: str
    indentation: str = "    "

    def __str__(self) -> str:
        return f"{self.indentation}{self.key} {self.value}".rstrip()


@dataclass
class SSHHost:
    patterns: List[str] = field(default_factory=list)
    options: List[SSHOption] = field(default_factory=list)
    start_line: int = -1
    end_line: int = -1
    raw_lines: List[str] = field(default_factory=list)

    @classmethod
    def from_raw_lines(cls, lines: List[str]) -> "SSHHost":
        host = cls()
        found_host_line = False
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                host.raw_lines.append(line)
                continue

            if stripped.lower().startswith("host ") and not found_host_line:
                patterns = stripped.split(None, 1)[1].split()
                host.patterns = patterns
                host.raw_lines.append(line)
                found_host_line = True
                continue
            elif stripped.lower().startswith("host ") and found_host_line:
                raise ValueError(
                    "Multiple Host declarations found within a single raw host block."
                )

            m = re.match(r"^(\S+)\s+(.+)$", stripped)
            if m:
                key, value = m.group(1), m.group(2)
                indentation = line[: len(line) - len(line.lstrip())]
                host.options.append(
                    SSHOption(key=key, value=value, indentation=indentation)
                )
                host.raw_lines.append(line)
            else:
                host.raw_lines.append(line)

        if not found_host_line:
            raise ValueError("No Host declaration found in raw host block.")

        return host

    def get_option(self, key: str) -> Optional[str]:
        for opt in self.options:
            if opt.key.lower() == key.lower():
                return opt.value
        return None

    def set_option(self, key: str, value: str) -> None:
        for opt in self.options:
            if opt.key.lower() == key.lower():
                opt.value = value
                return
        self.options.append(SSHOption(key=key, value=value))

    def remove_option(self, key: str) -> bool:
        for i, opt in enumerate(self.options):
            if opt.key.lower() == key.lower():
                del self.options[i]
                return True
        return False


@dataclass
class SSHConfig:
    file_path: Path
    hosts: List[SSHHost] = field(default_factory=list)
    global_options: List[SSHOption] = field(default_factory=list)
    include_directives: List[str] = field(default_factory=list)
    includes_resolved: Dict[Path, List[str]] = field(default_factory=dict)
    original_lines: List[str] = field(default_factory=list)

    def is_dirty(self) -> bool:
        current_content_lines = []
        for opt in self.global_options:
            current_content_lines.append(str(opt))
        if self.global_options and (
            not current_content_lines or current_content_lines[-1].strip() != ""
        ):
            current_content_lines.append("")
        for host in self.hosts:
            current_content_lines.append(f"Host {' '.join(host.patterns)}")
            for opt in host.options:
                current_content_lines.append(str(opt))
            current_content_lines.append("")
        while current_content_lines and current_content_lines[-1] == "":
            current_content_lines.pop()
        for inc in self.include_directives:
            current_content_lines.append(f"Include {inc}")

        original_clean_lines = [line.rstrip("\n") for line in self.original_lines]

        while original_clean_lines and original_clean_lines[-1] == "":
            original_clean_lines.pop()

        return current_content_lines != original_clean_lines

    def get_host(self, alias: str) -> Optional[SSHHost]:
        for h in self.hosts:
            if alias in h.patterns:
                return h
        return None

    def add_host(self, host: SSHHost) -> None:
        self.hosts.append(host)

    def remove_host(self, host: SSHHost) -> bool:
        try:
            self.hosts.remove(host)
            return True
        except ValueError:
            return False


class SSHConfigParser:
    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path: Path = config_path or Path.home() / ".ssh" / "config"
        self.config: SSHConfig = SSHConfig(file_path=self.config_path)
        self._have_backed_up_this_session: bool = False
        self.auto_backup_enabled: bool = True
        self.backup_dir: Optional[Path] = None

    def parse(self) -> SSHConfig:
        if not self.config_path.exists():
            logger.warning("SSH config file not found: %s", self.config_path)
            return self.config

        with self.config_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        self.config.original_lines = [l.rstrip("\n") for l in lines]

        self._parse_main_lines(self.config.original_lines)
        self._resolve_includes()
        return self.config

    def write(self, backup: bool = True) -> None:
        content = self._generate_content()

        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as f:
                    current = f.read()
                if current == content:
                    return
            except Exception:
                pass

        effective_backup = (
            backup and self.auto_backup_enabled and self.config_path.exists()
        )
        if effective_backup and not self._have_backed_up_this_session:
            self._backup_file()
            self._have_backed_up_this_session = True

        self._atomic_write(content)

    def validate(self) -> List[str]:
        errors: List[str] = []
        seen: Dict[str, SSHHost] = {}
        for host in self.config.hosts:
            for pat in host.patterns:
                if pat in seen:
                    errors.append(f"Duplicate host alias: {pat}")
                else:
                    seen[pat] = host
        for host in self.config.hosts:
            port = host.get_option("Port")
            if port:
                try:
                    p = int(port)
                    if p < 1 or p > 65535:
                        errors.append(
                            f"Invalid port for host {host.patterns[0]}: {port}"
                        )
                except ValueError:
                    errors.append(
                        f"Port is not an integer for host {host.patterns[0]}: {port}"
                    )
        for host in self.config.hosts:
            ident = host.get_option("IdentityFile")
            if ident:
                path = Path(ident).expanduser()
                if not path.is_absolute():
                    path = Path.home() / ".ssh" / ident
                if not path.exists():
                    errors.append(
                        f"IdentityFile not found for host {host.patterns[0]}: {ident}"
                    )
        return errors

    def _parse_main_lines(self, lines: List[str]) -> None:
        self.config.hosts.clear()
        self.config.global_options.clear()
        self.config.include_directives.clear()

        current_host: Optional[SSHHost] = None
        in_host = False

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                if in_host and current_host is not None:
                    current_host.raw_lines.append(line)
                continue

            if stripped.lower().startswith("include "):
                include_arg = stripped.split(None, 1)[1]
                self.config.include_directives.append(include_arg)
                continue

            if stripped.lower().startswith("host "):
                if current_host is not None:
                    current_host.end_line = idx - 1
                    self.config.hosts.append(current_host)
                patterns = stripped.split(None, 1)[1].split()
                current_host = SSHHost(
                    patterns=patterns, start_line=idx, raw_lines=[line]
                )
                in_host = True
                continue

            m = re.match(r"^(\S+)\s+(.+)$", stripped)
            if m:
                key, value = m.group(1), m.group(2)
                indentation = line[: len(line) - len(line.lstrip())]
                opt = SSHOption(key=key, value=value, indentation=indentation)
                if in_host and current_host is not None:
                    current_host.options.append(opt)
                    current_host.raw_lines.append(line)
                else:
                    self.config.global_options.append(opt)
                continue

            if in_host and current_host is not None:
                current_host.raw_lines.append(line)

        if current_host is not None:
            current_host.end_line = len(lines) - 1
            self.config.hosts.append(current_host)

    def _resolve_includes(self) -> None:
        resolved: Dict[Path, List[str]] = {}
        base_dir = self.config_path.parent
        for pattern in self.config.include_directives:
            expanded = os.path.expanduser(pattern)
            if not os.path.isabs(expanded):
                expanded = str(base_dir / expanded)

            try:
                matches = glob.glob(expanded, recursive=False)
                if not matches and "**" in expanded:
                    matches = glob.glob(expanded, recursive=True)
            except Exception:
                matches = []

            for path_str in matches:
                p = Path(path_str)
                try:
                    with p.open("r", encoding="utf-8") as f:
                        resolved[p] = f.readlines()
                except Exception:
                    continue

        self.config.includes_resolved = resolved

    def _backup_file(self) -> None:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        if self.backup_dir:
            target_dir = Path(self.backup_dir).expanduser()
        else:
            target_dir = self.config_path.parent
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            target_dir = self.config_path.parent
        backup = (target_dir / self.config_path.name).with_suffix(f".{ts}.bak")
        try:
            shutil.copy2(self.config_path, backup)
            logger.info("Backup created: %s", backup)
        except Exception as e:
            logger.warning("Failed to create backup: %s", e)

    def _generate_content(self) -> str:
        lines: List[str] = []
        for opt in self.config.global_options:
            lines.append(str(opt))
        if self.config.global_options and (not lines or lines[-1] != ""):
            lines.append("")
        for host in self.config.hosts:
            lines.append(f"Host {' '.join(host.patterns)}")
            for opt in host.options:
                lines.append(str(opt))
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
        for inc in self.config.include_directives:
            lines.append(f"Include {inc}")
        return "\n".join(lines) + "\n"

    def _atomic_write(self, content: str) -> None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.config_path.parent),
            delete=False,
        )
        tmp_path = Path(tmp.name)
        try:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            if self.config_path.exists():
                st = self.config_path.stat()
                os.chmod(tmp_path, stat.S_IMODE(st.st_mode))
            else:
                os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.config_path)
        except Exception:
            try:
                tmp.close()
            except Exception:
                pass
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise
