import hashlib
import re
from typing import Any, Optional
from app.core.exceptions import ValidationException


class PromptEngine:
    """Core prompt compilation, placeholder variable resolution, and hashing engine."""

    PLACEHOLDER_REGEX = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_\.]*)\s*\}\}")

    @staticmethod
    def extract_variables(template_text: str) -> list[str]:
        """Parses a prompt template and returns all unique dot-notated variable paths."""
        if not template_text:
            return []
        matches = PromptEngine.PLACEHOLDER_REGEX.findall(template_text)
        seen = set()
        unique_vars = []
        for var in matches:
            if var not in seen:
                seen.add(var)
                unique_vars.append(var)
        return unique_vars

    @staticmethod
    def resolve_path(context: Any, path: str) -> Any:
        """Helper to recursively resolve dotted path variables in the execution context."""
        parts = path.split(".")
        current = context
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
        return current

    @classmethod
    def compile(cls, template_text: str, context: dict[str, Any], strict: bool = True) -> str:
        """Substitutes variables inside prompt templates with context dictionary values.
        
        Raises:
            ValidationException if a required placeholder path cannot be resolved in strict mode.
        """
        if not template_text:
            return ""

        required_vars = cls.extract_variables(template_text)
        resolved_context = {}
        for var in required_vars:
            val = cls.resolve_path(context, var)
            if val is None:
                if strict:
                    raise ValidationException(f"Prompt compilation failed: missing required variable '{var}'")
                resolved_context[var] = ""
            else:
                resolved_context[var] = str(val)

        def replace_match(match):
            var_name = match.group(1).strip()
            return resolved_context.get(var_name, "")

        return cls.PLACEHOLDER_REGEX.sub(replace_match, template_text)

    @staticmethod
    def compute_hash(prompt_text: str) -> str:
        """Generates a reproducible SHA-256 hash for auditing and caching compiled prompts."""
        return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


# Redis-ready Prompt Cache interface
class CompiledPromptCache:
    """Caching layer to retrieve compiled prompts. Ready to plug into Redis."""
    _cache: dict[str, str] = {}

    @classmethod
    def get(cls, prompt_hash: str) -> Optional[str]:
        return cls._cache.get(prompt_hash)

    @classmethod
    def set(cls, prompt_hash: str, compiled_prompt: str) -> None:
        cls._cache[prompt_hash] = compiled_prompt

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()
