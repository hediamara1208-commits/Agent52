"""Instruction_Loader (Req. 21.4-21.8).

Composes the System_Prompt of an agent from its Instruction_File and the
Skill_Files it lists, and computes the Instruction_Hash recorded in the Trace.

Layout under ``root`` (config ``instruction_dir``, default ``guide/agents``)::

    instructions/<agent>.md
    skills/<skill>.md
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Mapping, Sequence

GUIDANCE_ONLY_SKILL = "guidance_only"
_SECTION_RE = re.compile(r"^#\s+included skills\s*$", re.IGNORECASE)
_HEADING_RE = re.compile(r"^#\s+\S")
_SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


class InstructionError(Exception):
    """An Instruction_File or Skill_File is missing or invalid (Req. 21.5, 21.6)."""

    def __init__(self, agent: str, missing_file: str, reason: str | None = None) -> None:
        self.agent = agent
        self.missing_file = missing_file
        self.reason = reason or "file not found"
        super().__init__(f"{agent}: {missing_file}: {self.reason}")


@dataclass(frozen=True)
class SystemPrompt:
    agent: str
    text: str  # Instruction_File text, then each listed Skill_File text, in the listed order
    skills: tuple[str, ...]
    instruction_hash: str  # SHA-256 hex of the UTF-8 text with LF line endings


def _read(agent: str, path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as error:
        raise InstructionError(agent, str(path)) from error
    except (OSError, UnicodeDecodeError) as error:
        raise InstructionError(agent, str(path), f"unreadable: {error.__class__.__name__}") from error
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def _listed_skills(agent: str, instruction_path: Path, text: str) -> tuple[str, ...]:
    skills: list[str] = []
    in_section = False
    found = False
    for line in text.split("\n"):
        stripped = line.strip()
        if _SECTION_RE.match(stripped):
            in_section, found = True, True
            continue
        if in_section and _HEADING_RE.match(stripped):
            break
        if in_section and stripped:
            name = stripped[1:].strip() if stripped.startswith(("-", "*")) else stripped
            if not _SKILL_NAME_RE.match(name):
                raise InstructionError(agent, str(instruction_path), f"invalid skill name {name!r}")
            if name not in skills:
                skills.append(name)
    if not found:
        raise InstructionError(agent, str(instruction_path), "missing 'Included skills' section")
    return tuple(skills)


def load_system_prompt(agent: str, root: Path) -> SystemPrompt:
    """Compose the System_Prompt of ``agent``; raise InstructionError on any problem."""
    if not agent or not _SKILL_NAME_RE.match(agent):
        raise InstructionError(agent, "<instruction file>", "invalid agent name")
    root = Path(root)
    instruction_path = root / "instructions" / f"{agent}.md"
    instruction_text = _read(agent, instruction_path)
    skills = _listed_skills(agent, instruction_path, instruction_text)

    skill_texts: dict[str, str] = {}
    for name in skills:
        skill_texts[name] = _read(agent, root / "skills" / f"{name}.md")

    if GUIDANCE_ONLY_SKILL not in skills:
        raise InstructionError(agent, f"{GUIDANCE_ONLY_SKILL}.md", "guidance_only skill is not listed")

    parts = [instruction_text.rstrip("\n")]
    for name in skills:
        parts.append(f"# Skill: {name}\n{skill_texts[name].strip(chr(10))}")
    text = "\n\n".join(parts) + "\n"

    guidance = skill_texts[GUIDANCE_ONLY_SKILL].strip()
    if not guidance or guidance not in text:
        raise InstructionError(agent, f"{GUIDANCE_ONLY_SKILL}.md", "System_Prompt lacks the guidance_only text")

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SystemPrompt(agent=agent, text=text, skills=skills, instruction_hash=digest)


def load_all(agents: Sequence[str], root: Path) -> Mapping[str, SystemPrompt]:
    """Load every agent's System_Prompt; the first error is raised (no session starts)."""
    return {agent: load_system_prompt(agent, root) for agent in agents}
