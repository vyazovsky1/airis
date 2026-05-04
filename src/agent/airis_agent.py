"""AIRIS agent — agentic loop over OpenAI + MCP tools."""

import json
import os
from typing import Optional

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from core.config import config
from core.logger import get_logger
from core.utils import load_prompt
from agent.config import agent_config
from agent.mcp_manager import MCPManager
import core.token_stats as token_stats

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic output models
# ---------------------------------------------------------------------------

class ResourceRequests(BaseModel):
    cpu: str
    memory: str
    storage: Optional[str] = None

class ResourceLimits(BaseModel):
    cpu: str
    memory: str

class TargetResources(BaseModel):
    requests: ResourceRequests
    limits: ResourceLimits

class DeploymentDecision(BaseModel):
    deployment_name: str
    reasoning: str
    target_resources: TargetResources

class AirisDecision(BaseModel):
    decision: str
    reasoning: str
    deployments: list[DeploymentDecision]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def _build_system_prompt(mode: str) -> str:
    """
    Assemble the system prompt for the given mode.
    Shared sections are always included; tools_{mode}.txt is action-specific.
    All content is combined into a single system message (one role=system turn).
    """
    parts = [
        load_prompt("system_main.txt", component="agent"),
        load_prompt(f"tools_{mode}.txt", component="agent"),      # action-specific workflow
        load_prompt("analyse_resources.txt", component="agent"),
        load_prompt("storage_gate.txt", component="agent"),
        load_prompt("confidence_calibration.txt", component="agent"),
        load_prompt("resource_validation.txt", component="agent"),
    ]
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _describe_turn_context(history: list) -> str:
    """Return a brief label for what's driving this LLM call."""
    if not history:
        return "initial"
    last = history[-1]
    role = last.get("role") if isinstance(last, dict) else getattr(last, "role", None)

    if role == "user":
        content = last.get("content") if isinstance(last, dict) else getattr(last, "content", "")
        snippet = (content or "")[:100].replace("\n", " ")
        return f'user: "{snippet}"'

    if role == "tool":
        # Walk back to find the assistant turn that issued these tool calls
        for msg in reversed(history):
            msg_role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
            if msg_role == "assistant":
                tcs = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
                if tcs:
                    names = [
                        (tc["function"]["name"] if isinstance(tc, dict) else tc.function.name)
                        for tc in tcs
                    ]
                    return f"tool results: {', '.join(names)}"
        return "tool results"

    return f"role={role}"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class AirisAgent:
    """AIRIS agent with two analysis modes sharing a common tool-call loop."""

    def __init__(self, mcp: MCPManager, model_name: Optional[str] = None) -> None:
        self._mcp = mcp
        self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "mock-key"))
        self._model = model_name or config.OPENAI_DEFAULT_MODEL
        self._temperature = config.TEMPERATURE

    def _fresh_history(self, mode: str) -> list[ChatCompletionMessageParam]:
        return [{"role": "system", "content": _build_system_prompt(mode)}]

    # ── Public entry points ─────────────────────────────────────────────────

    async def run_k8s_analysis(self, namespace: str) -> Optional[AirisDecision]:
        """
        Case 1: Analyze current K8s metrics in a namespace.
        System prompt: tools_k8s.txt. No PR required.
        """
        logger.info("Mode: K8s analysis — namespace '%s'", namespace)
        history = self._fresh_history("k8s")
        history.append({"role": "user", "content": f"Analyze namespace '{namespace}'."})
        return await self._agent_loop(history)

    async def run_pr_review(self, pr_number: int, namespace: str) -> Optional[AirisDecision]:
        """
        Case 2: Review a PR for resource allocation impact.
        System prompt: tools_pr.txt. K8s tools are optional.
        """
        logger.info("Mode: PR review — PR #%d, namespace '%s'", pr_number, namespace)
        history = self._fresh_history("pr")
        history.append({"role": "user", "content": f"Review PR #{pr_number} in namespace '{namespace}'."})
        return await self._agent_loop(history)

    # ── Shared tool-call loop ───────────────────────────────────────────────

    async def _agent_loop(
        self, history: list[ChatCompletionMessageParam]
    ) -> Optional[AirisDecision]:
        """
        Run the agentic tool-call loop until the LLM produces a valid
        AirisDecision JSON response or the turn limit is reached.
        """
        token_stats.reset()
        tools = self._mcp.tools
        max_turns = agent_config.MAX_AGENT_TURNS
        max_retries = agent_config.MAX_SELF_CORRECTION_RETRIES
        
        result: Optional[AirisDecision] = None
        retries = 0
        last_invalid_content: Optional[str] = None

        try:
            for turn in range(1, max_turns + 1):
                logger.info(
                    "Agentic loop turn %d/%d (Retries: %d/%d) — %s",
                    turn, max_turns, retries, max_retries, _describe_turn_context(history),
                )

                kwargs: dict = {}
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                # DEBUG: full request sent to LLM
                logger.debug(
                    "LLM request → model=%s  messages=%d  tools=%d",
                    self._model, len(history), len(tools)
                )

                response = self._client.chat.completions.create(
                    model=self._model,
                    temperature=self._temperature,
                    messages=history,
                    **kwargs,
                )

                message = response.choices[0].message

                if response.usage:
                    token_stats.record(
                        "thinking",
                        response.usage.prompt_tokens,
                        response.usage.completion_tokens,
                    )

                history.append(message)  # type: ignore[arg-type]

                # ── Tool calls ──────────────────────────────────────────────
                if message.tool_calls:
                    if message.content:
                        logger.debug("LLM reasoning: %s", message.content)
                    logger.info(
                        "LLM called %d tool(s): %s",
                        len(message.tool_calls),
                        ", ".join(tc.function.name for tc in message.tool_calls),
                    )

                    for tc in message.tool_calls:
                        fn_name = tc.function.name
                        try:
                            fn_args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            fn_args = {}

                        logger.info("  >> %s(%s)", fn_name, fn_args)
                        tool_result = await self._mcp.call_tool(fn_name, fn_args)
                        history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_result,
                        })
                    continue  # feed results back to LLM

                # ── No tool calls — attempt to parse final JSON answer ────────
                content = message.content or ""
                
                # Loop protection: detect if model is repeating invalid output
                if content == last_invalid_content:
                    logger.warning("LLM is repeating the same invalid content. Escalating prompt.")
                    feedback_prefix = "[SYSTEM]: CRITICAL: You are repeating the same invalid output. "
                else:
                    feedback_prefix = "[SYSTEM]: "

                try:
                    # Fuzzy JSON extraction
                    raw_json = content
                    if "```json" in content:
                        raw_json = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        raw_json = content.split("```")[1].split("```")[0]
                    
                    raw_json = raw_json.strip()
                    
                    # If still not parsing, try to find the first '{' and last '}'
                    if not (raw_json.startswith("{") and raw_json.endswith("}")):
                        start = raw_json.find("{")
                        end = raw_json.rfind("}")
                        if start != -1 and end != -1:
                            raw_json = raw_json[start : end + 1]

                    result = AirisDecision.model_validate_json(raw_json)
                    logger.info("AirisDecision validated successfully.")
                    return result

                except (ValidationError, Exception) as e:
                    retries += 1
                    last_invalid_content = content
                    
                    if retries > max_retries:
                        logger.error("AirisAgent: exceeded max formatting retries (%d).", max_retries)
                        break

                    logger.warning("JSON parse/validation failed (Retry %d/%d): %s", retries, max_retries, e)
                    
                    history.append({
                        "role": "user",
                        "content": (
                            f"{feedback_prefix}Your previous output failed JSON validation: {e}. "
                            "Please fix the schema and output ONLY the raw JSON object. "
                            "Ensure 'deployments' is a list and all 'target_resources' are correctly nested."
                        ),
                    })

            logger.error("AirisAgent: loop terminated without a valid decision.")
            return None

        finally:
            token_stats.log_summary()
