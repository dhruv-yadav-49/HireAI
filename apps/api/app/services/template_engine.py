import re
from typing import Any, Optional
from app.core.exceptions import ValidationException


class TemplateEngine:
    """Core rendering and validation engine for communication templates."""

    # Regex to find placeholders: {{ lead.first_name }}
    PLACEHOLDER_REGEX = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_\.]*)\s*\}\}")

    @staticmethod
    def extract_variables(template_text: str) -> list[str]:
        """Parses a template body or subject and extracts all placeholder variable paths."""
        if not template_text:
            return []
        # Find all matches
        matches = TemplateEngine.PLACEHOLDER_REGEX.findall(template_text)
        # Return unique variables, preserving order
        seen = set()
        unique_vars = []
        for var in matches:
            if var not in seen:
                seen.add(var)
                unique_vars.append(var)
        return unique_vars

    @staticmethod
    def resolve_path(obj: Any, path: str) -> Any:
        """Helper to recursively resolve dotted paths on dictionaries or objects.
        
        Example: resolve_path(lead, "first_name") or resolve_path(context, "lead.first_name")
        """
        parts = path.split(".")
        current = obj
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
        return current

    @staticmethod
    def render(
        template_body: str,
        template_subject: Optional[str],
        context: dict[str, Any],
        render_engine_version: int = 1
    ) -> tuple[str, Optional[str]]:
        """Renders subject and body templates using the provided dot-notated context.
        
        Raises:
            ValidationException if a required variable placeholder cannot be resolved.
        """
        # 1. Extract variables from body & subject
        body_vars = TemplateEngine.extract_variables(template_body)
        subject_vars = TemplateEngine.extract_variables(template_subject or "")
        all_required = list(set(body_vars + subject_vars))

        # 2. Verify all placeholders can be resolved from context
        missing_vars = []
        resolved_context = {}
        for var in all_required:
            val = TemplateEngine.resolve_path(context, var)
            if val is None:
                # Missing context variable
                missing_vars.append(var)
            else:
                resolved_context[var] = str(val)

        if missing_vars:
            raise ValidationException(
                f"Template variables missing or unresolved in rendering context: {', '.join(missing_vars)}"
            )

        # 3. Perform string substitutions
        def replacer(match):
            var_name = match.group(1)
            return resolved_context.get(var_name, "")

        rendered_body = TemplateEngine.PLACEHOLDER_REGEX.sub(replacer, template_body)
        rendered_subject = None
        if template_subject:
            rendered_subject = TemplateEngine.PLACEHOLDER_REGEX.sub(replacer, template_subject)

        return rendered_body, rendered_subject

    @staticmethod
    def validate_template_rules(
        channel: str,
        subject: Optional[str],
        body: str
    ) -> None:
        """Performs validation checks on channel specific template rules.
        
        Raises ValidationException if checks fail.
        """
        if not body or not body.strip():
            raise ValidationException("Template body template cannot be empty.")

        channel_upper = channel.upper()
        if channel_upper == "EMAIL":
            if not subject or not subject.strip():
                raise ValidationException("Email templates require a subject_template.")
        elif channel_upper == "SMS":
            if len(body) > 160:
                # Warning constraint (can be log warning or validator warning, let's log or raise warning detail if strict)
                pass
