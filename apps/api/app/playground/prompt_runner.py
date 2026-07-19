"""
app/playground/prompt_runner.py

Prompt Execution Engine.

CTO Refinement #6: SHA-256 hash tracking for prompt_hash and compiled_prompt_hash.
Compiles templates and runs dispatches through SandboxRuntime without production side-effects.
"""
import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional

from app.playground.model_selector import ModelSelector
from app.playground.playground_context import PlaygroundContext
from app.playground.sandbox_runtime import SandboxRuntime
from app.services.llm_provider_registry import LLMProviderRegistry


@dataclass
class PromptRunResult:
    prompt_text: str
    compiled_prompt: str
    output_text: str
    prompt_hash: str
    compiled_prompt_hash: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    token_cost: float
    model_name: str


class PromptRunner:
    """Compiles and executes prompts in the Sandbox environment."""

    def __init__(self, ctx: PlaygroundContext) -> None:
        self.ctx = ctx
        self.sandbox = SandboxRuntime(ctx)

    def compile_prompt(self, template: str, variables: Dict[str, Any]) -> str:
        """Compile variables into template string."""
        compiled = template
        for k, v in variables.items():
            compiled = compiled.replace(f"{{{{{k}}}}}", str(v))
        return compiled

    async def run_prompt(
        self,
        template: str,
        variables: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> PromptRunResult:
        vars_dict = variables or {}
        model = model_name or self.ctx.model_name
        temp = temperature if temperature is not None else self.ctx.temperature
        max_t = max_tokens or self.ctx.max_tokens

        compiled = self.compile_prompt(template, vars_dict)

        # CTO Refinement #6: Hash tracking
        prompt_hash = hashlib.sha256(template.encode("utf-8")).hexdigest()
        compiled_hash = hashlib.sha256(compiled.encode("utf-8")).hexdigest()

        start_t = time.monotonic()

        # If sandbox is MOCK_EXTERNALS or using MOCK provider, generate synthetic response
        if self.sandbox.is_mock_externals() or self.ctx.provider.value == "MOCK":
            output_text = (
                f"[SANDBOX MOCK RESPONSE for model {model} (temp={temp})]\n"
                f"Processed prompt (hash: {compiled_hash[:8]}):\n{compiled[:200]}"
            )
            input_tokens = len(compiled.split())
            output_tokens = len(output_text.split())
        else:
            provider_instance = LLMProviderRegistry.get_provider(self.ctx.provider)
            output_text = await provider_instance.generate_response(
                prompt=compiled,
                temperature=temp,
                max_tokens=max_t,
            )
            input_tokens = len(compiled.split())
            output_tokens = len(output_text.split())

        latency_ms = int((time.monotonic() - start_t) * 1000)
        cost = ModelSelector.estimate_cost(model, input_tokens, output_tokens)

        return PromptRunResult(
            prompt_text=template,
            compiled_prompt=compiled,
            output_text=output_text,
            prompt_hash=prompt_hash,
            compiled_prompt_hash=compiled_hash,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            token_cost=cost,
            model_name=model,
        )
