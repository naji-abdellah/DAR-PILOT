"""DarPilot Agent with tools and guardrails (M4).

Provides a tool-using agent that can search listings, create leads, book visits,
and escalate to human. All tool calls are validated, rate-limited, and logged
to the audit log.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

import requests

from ai.llm import LLMClient, get_llm_client
from ai import rag
from backend import services


# ── Guardrails Configuration ──────────────────────────────────────────────

# Maximum number of tool iterations per conversation
MAX_ITERATIONS = 5

# Allowed tool names (allowlist)
ALLOWED_TOOLS = frozenset(["search_listings", "create_lead", "book_visit", "escalate_to_human"])

# Maximum length for tool string arguments
MAX_TOOL_ARG_LEN = 500

# PII patterns to redact before sending to LLM
# Anchored Moroccan phone formats only — avoids false positives on prices/years
PII_PATTERNS = [
    (re.compile(r"\b\d{10}\b"), "[PHONE]"),  # 10-digit phone
    (re.compile(r"\b0[5-7]\d{8}\b"), "[PHONE]"),  # Moroccan mobile (05xxxxxxxx through 07xxxxxxxx)
    (re.compile(r"\+212\s?[5-7]\d{8}\b"), "[PHONE]"),  # +212 prefix
    (re.compile(r"\b00212\s?[5-7]\d{8}\b"), "[PHONE]"),  # 00212 prefix
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
]

# ── Prompt Injection Detection Patterns ────────────────────────────────────

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    # Direct instruction overrides (English)
    (re.compile(r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions?", re.IGNORECASE), "instruction_override"),
    (re.compile(r"forget\s+(?:all\s+)?(?:previous\s+)?instructions?", re.IGNORECASE), "instruction_override"),
    (re.compile(r"disregard\s+(?:all\s+)?(?:previous\s+)?instructions?", re.IGNORECASE), "instruction_override"),
    (re.compile(r"override\s+(?:all\s+)?(?:previous\s+)?instructions?", re.IGNORECASE), "instruction_override"),
    # Direct instruction overrides (Spanish)
    (re.compile(r"ignora\s+(?:todas\s+)?(?:las\s+)?instrucciones?", re.IGNORECASE), "instruction_override"),
    (re.compile(r"olvida\s+(?:todas\s+)?(?:las\s+)?instrucciones?", re.IGNORECASE), "instruction_override"),
    # Direct instruction overrides (French)
    (re.compile(r"ignore\s+(?:toutes\s+)?(?:les\s+)?instructions?", re.IGNORECASE), "instruction_override"),
    (re.compile(r"oublie\s+(?:toutes\s+)?(?:les\s+)?instructions?", re.IGNORECASE), "instruction_override"),
    # Role-play jailbreaks
    (re.compile(r"pretend\s+(?:you\s+are|to\s+be)\s+\w+", re.IGNORECASE), "roleplay_jailbreak"),
    (re.compile(r"you\s+are\s+(?:now\s+)?(?:dan|unrestricted|unfiltered|unlimited)", re.IGNORECASE), "roleplay_jailbreak"),
    (re.compile(r"do\s+anything\s+now", re.IGNORECASE), "roleplay_jailbreak"),
    (re.compile(r"no\s+rules?", re.IGNORECASE), "roleplay_jailbreak"),
    (re.compile(r"act\s+as\s+(?:an?\s+)?(?:unrestricted|unfiltered)", re.IGNORECASE), "roleplay_jailbreak"),
    # System prompt extraction
    (re.compile(r"(?:show|give|tell|output|print|repeat|display)\s+(?:me\s+)?(?:your\s+)?(?:system\s+)?prompt", re.IGNORECASE), "system_prompt_leak"),
    (re.compile(r"(?:what\s+is|show\s+me)\s+(?:your\s+)?(?:system\s+)?(?:instructions?|prompt)", re.IGNORECASE), "system_prompt_leak"),
    (re.compile(r"repeat\s+(?:the\s+)?(?:above|previous|full|entire)\s+(?:prompt|instructions?)", re.IGNORECASE), "system_prompt_leak"),
    (re.compile(r"(?:reveal|expose|leak)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions?)", re.IGNORECASE), "system_prompt_leak"),
    # Tool abuse - unauthorized tools
    (re.compile(r"(?:call|invoke|execute|run)\s+(?:delete|drop|admin|shell|exec|database)", re.IGNORECASE), "tool_abuse"),
    (re.compile(r"(?:call|invoke|execute|run)\s+(?:the\s+|a\s+|an\s+)?(?:delete_database|drop_table|admin_access)", re.IGNORECASE), "tool_abuse"),
    (re.compile(r"(?:book_visit|create_lead|search_listings)\s*\([^)]*(?:drop|delete|union|select\s+\*)", re.IGNORECASE), "tool_abuse"),
    # Tool abuse - direct tool calls in user input
    (re.compile(r"(?:call|invoke|use)\s+(?:book_visit|create_lead|search_listings|escalate_to_human)\s+(?:with|for)", re.IGNORECASE), "tool_abuse"),
    (re.compile(r"(?:book_visit|create_lead)\s+(?:lead_id|listing_id)\s*=", re.IGNORECASE), "tool_abuse"),
    # Bypass human approval
    (re.compile(r"(?:no\s+need|without|bypass|skip)\s+(?:human\s+)?(?:approval|confirmation)", re.IGNORECASE), "bypass_approval"),
    (re.compile(r"(?:no\s+need|without)\s+for\s+(?:human\s+)?(?:approval|confirmation)", re.IGNORECASE), "bypass_approval"),
    # PII extraction
    (re.compile(r"(?:show|give|list|get|extract|dump)\s+(?:all\s+)?(?:leads?|users?|contacts?|customers?)\s+(?:with\s+)?(?:phone|email|ssn|credit|address)", re.IGNORECASE), "pii_extraction"),
    (re.compile(r"(?:phone|email|contact)\s+(?:numbers?|addresses?)\s+(?:of|for)\s+(?:all\s+)?(?:leads?|users?)", re.IGNORECASE), "pii_extraction"),
    # Database schema extraction
    (re.compile(r"(?:database|table|schema)\s+(?:structure|columns?|names?|tables?)", re.IGNORECASE), "schema_extraction"),
    (re.compile(r"(?:what\s+(?:tables?|columns?)|list\s+(?:tables?|columns?))\s+(?:in|from)\s+(?:your\s+)?(?:database|db)", re.IGNORECASE), "schema_extraction"),
    # Encoded/obfuscated (basic unicode escape detection)
    (re.compile(r"\\u[0-9a-fA-F]{4}"), "encoded_injection"),
    (re.compile(r"%[0-9a-fA-F]{2}"), "encoded_injection"),  # URL encoding
    # Emotional manipulation
    (re.compile(r"(?:grandmother|mother|father|dying|emergency|urgent|please\s+help).*?(?:must|have\s+to|need\s+to)\s+(?:ignore|bypass|override|give)", re.IGNORECASE), "emotional_manipulation"),
    # Mass/recursive tool invocation (DoS)
    (re.compile(r"(?:search|create|book)\s+(?:for\s+)?(?:100|50|20|many|multiple|all)\s+(?:listings?|leads?|visits?)", re.IGNORECASE), "mass_invocation"),
    (re.compile(r"(?:repeat|loop|iterate)\s+(?:search|create|book)\s+(?:for|times?)", re.IGNORECASE), "recursive_invocation"),
    # Pattern injection (mimicking RAG prompt format)
    (re.compile(r"listings?:?\s*\n\s*-?\s*\[\s*id\s*:", re.IGNORECASE), "pattern_injection"),
    (re.compile(r"question:?\s*\n\s*answer:?", re.IGNORECASE), "pattern_injection"),
]

# Maximum input length to prevent DoS
MAX_INPUT_LENGTH = 2000

# Maximum conversation history length
MAX_HISTORY_LENGTH = 20


# ── Tool Schemas and Validation ───────────────────────────────────────────

@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None


class Tool:
    """Base class for agent tools with validation."""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema

    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize tool arguments. Raises ValueError on invalid input."""
        raise NotImplementedError

    def execute(self, args: Dict[str, Any], user_id: Optional[int] = None) -> ToolResult:
        """Execute the tool with validated arguments."""
        raise NotImplementedError


class SearchListingsTool(Tool):
    """Search listings via RAG."""

    name = "search_listings"
    description = "Search real estate listings by semantic similarity"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 200},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "").strip()
        if not query:
            raise ValueError("query is required and cannot be empty")
        if len(query) > 200:
            raise ValueError("query exceeds maximum length of 200 characters")
        top_k = args.get("top_k", 5)
        if not isinstance(top_k, int) or top_k < 1 or top_k > 10:
            raise ValueError("top_k must be an integer between 1 and 10")
        return {"query": query, "top_k": top_k}

    def execute(self, args: Dict[str, Any], user_id: Optional[int] = None) -> ToolResult:
        try:
            results = rag.search(args["query"], top_k=args["top_k"])
            return ToolResult(success=True, data=results)
        except Exception as exc:
            return ToolResult(success=False, error=f"Search failed: {exc}")


class CreateLeadTool(Tool):
    """Create a new lead (public capture)."""

    name = "create_lead"
    description = "Capture a new lead from a potential buyer"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
            "phone": {"type": "string", "maxLength": 20},
            "email": {"type": "string", "format": "email", "maxLength": 255},
            "message": {"type": "string", "maxLength": 2000},
            "listing_id": {"type": "integer", "minimum": 1},
        },
        "required": ["name", "email"],
        "additionalProperties": False,
    }

    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name", "").strip()
        if not name:
            raise ValueError("name is required")
        if len(name) > 100:
            raise ValueError("name exceeds maximum length of 100 characters")

        email = args.get("email", "").strip()
        if not email or "@" not in email:
            raise ValueError("valid email is required")
        if len(email) > 255:
            raise ValueError("email exceeds maximum length of 255 characters")

        phone = args.get("phone", "").strip() if args.get("phone") else None
        if phone and len(phone) > 20:
            raise ValueError("phone exceeds maximum length of 20 characters")

        message = args.get("message", "").strip() if args.get("message") else ""
        if len(message) > 2000:
            raise ValueError("message exceeds maximum length of 2000 characters")

        listing_id = args.get("listing_id")
        if listing_id is not None and (not isinstance(listing_id, int) or listing_id < 1):
            raise ValueError("listing_id must be a positive integer or omitted")

        return {
            "name": name,
            "email": email,
            "phone": phone,
            "message": message,
            "listing_id": listing_id,
        }

    def execute(self, args: Dict[str, Any], user_id: Optional[int] = None) -> ToolResult:
        try:
            validated = self.validate_args(args)
            lead = services.create_lead(
                name=validated["name"],
                phone=validated["phone"],
                email=validated["email"],
                message=validated["message"],
                listing_id=validated["listing_id"],
            )
            return ToolResult(success=True, data=lead)
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"Failed to create lead: {exc}")


class BookVisitTool(Tool):
    """Book a visit for a lead (requires human approval)."""

    name = "book_visit"
    description = "Schedule a property visit for a lead (requires human approval)"
    parameters = {
        "type": "object",
        "properties": {
            "lead_id": {"type": "integer", "minimum": 1},
            "listing_id": {"type": "integer", "minimum": 1},
            "scheduled_at": {"type": "string", "minLength": 10, "maxLength": 50},
            "notes": {"type": "string", "maxLength": 1000},
        },
        "required": ["lead_id", "listing_id", "scheduled_at"],
        "additionalProperties": False,
    }

    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        lead_id = args.get("lead_id")
        if not isinstance(lead_id, int) or lead_id < 1:
            raise ValueError("lead_id must be a positive integer")

        listing_id = args.get("listing_id")
        if not isinstance(listing_id, int) or listing_id < 1:
            raise ValueError("listing_id must be a positive integer")

        scheduled_at = args.get("scheduled_at", "").strip()
        if not scheduled_at:
            raise ValueError("scheduled_at is required")
        if len(scheduled_at) < 10:
            raise ValueError("scheduled_at must be a valid datetime string (e.g., 2026-01-15T10:00:00)")

        notes = args.get("notes", "").strip() if args.get("notes") else ""
        if len(notes) > 1000:
            raise ValueError("notes exceeds maximum length of 1000 characters")

        return {
            "lead_id": lead_id,
            "listing_id": listing_id,
            "scheduled_at": scheduled_at,
            "notes": notes,
        }

    def execute(self, args: Dict[str, Any], user_id: Optional[int] = None) -> ToolResult:
        # Note: Human approval is enforced at the agent level, not here
        try:
            validated = self.validate_args(args)
            visit = services.create_visit(
                lead_id=validated["lead_id"],
                listing_id=validated["listing_id"],
                scheduled_at=validated["scheduled_at"],
                notes=validated["notes"],
            )
            return ToolResult(success=True, data=visit)
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"Failed to book visit: {exc}")


class EscalateToHumanTool(Tool):
    """Escalate to a human agent."""

    name = "escalate_to_human"
    description = "Escalate the conversation to a human agent"
    parameters = {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "minLength": 1, "maxLength": 500},
            "summary": {"type": "string", "maxLength": 1000},
        },
        "required": ["reason"],
        "additionalProperties": False,
    }

    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        reason = args.get("reason", "").strip()
        if not reason:
            raise ValueError("reason is required")
        if len(reason) > 500:
            raise ValueError("reason exceeds maximum length of 500 characters")

        summary = args.get("summary", "").strip() if args.get("summary") else ""
        if len(summary) > 1000:
            raise ValueError("summary exceeds maximum length of 1000 characters")

        return {"reason": reason, "summary": summary}

    def execute(self, args: Dict[str, Any], user_id: Optional[int] = None) -> ToolResult:
        # This tool doesn't create a DB record; it just signals escalation
        validated = self.validate_args(args)
        return ToolResult(
            success=True,
            data={"escalated": True, "reason": validated["reason"], "summary": validated["summary"]},
        )


# ── Tool Registry ──────────────────────────────────────────────────────────

TOOLS: Dict[str, Tool] = {
    "search_listings": SearchListingsTool(),
    "create_lead": CreateLeadTool(),
    "book_visit": BookVisitTool(),
    "escalate_to_human": EscalateToHumanTool(),
}


# ── PII Redaction ──────────────────────────────────────────────────────────

def redact_pii(text: str) -> str:
    """Redact common PII patterns from text before sending to LLM."""
    result = text
    for pattern, replacement in PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


# ── Prompt Injection Detection ───────────────────────────────────────────────

def detect_injection(text: str) -> Optional[Dict[str, Any]]:
    """Detect prompt injection attempts in user input.

    Returns a dict with attack_type and pattern if detected, None otherwise.
    """
    for pattern, attack_type in INJECTION_PATTERNS:
        if pattern.search(text):
            return {"attack_type": attack_type, "pattern": pattern.pattern}
    return None


def validate_input(text: str) -> Optional[str]:
    """Validate user input for safety.

    Returns error message if input is rejected, None if allowed.
    """
    # Length check
    if len(text) > MAX_INPUT_LENGTH:
        return f"Input exceeds maximum length of {MAX_INPUT_LENGTH} characters"

    # Injection detection
    injection = detect_injection(text)
    if injection:
        return f"Input blocked: detected {injection['attack_type']}"

    return None


# ── Audit Logging ──────────────────────────────────────────────────────────

def log_agent_action(
    user_id: Optional[int],
    action: str,
    tool_name: str,
    args: Dict[str, Any],
    result: ToolResult,
) -> None:
    """Log an agent tool invocation to audit_log."""
    details = {
        "tool": tool_name,
        "args": args,
        "success": result.success,
        "error": result.error,
    }
    try:
        services.log_action(
            user_id=user_id,
            action=action,
            table_name="agent_actions",
            record_id=None,
            details=json.dumps(details, ensure_ascii=False),
        )
    except Exception:
        # Never let audit logging break the main flow
        pass


# ── n8n Alerting ────────────────────────────────────────────────────────────

def alert_blocked_prompt(
    user_id: Optional[int],
    attack_type: str,
    payload: str,
    ip: Optional[str] = None,
) -> bool:
    """Send blocked prompt alert via the service layer (routes to n8n webhook)."""
    return services.alert_blocked_prompt(
        user_id=user_id,
        attack_type=attack_type,
        payload=payload,
        ip=ip,
    )


# ── Agent ──────────────────────────────────────────────────────────────────

class Agent:
    """Tool-using agent with guardrails."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        max_iterations: int = MAX_ITERATIONS,
        require_human_approval_for_booking: bool = True,
    ):
        self.llm = llm_client or get_llm_client()
        self.max_iterations = max_iterations
        self.require_human_approval_for_booking = require_human_approval_for_booking
        self.tools = TOOLS

    def _build_system_prompt(self) -> str:
        """Load system prompt from versioned file."""
        try:
            with open("prompts/agent_system_v1.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        return (
            "You are a helpful real-estate assistant for a fictional Moroccan agency.\n"
            "You have access to tools: search_listings, create_lead, book_visit, escalate_to_human.\n"
            "Rules:\n"
            "- Always search listings before recommending properties\n"
            "- Create a lead when the user shows interest\n"
            "- Book visits ONLY after human approval (you must ask for confirmation)\n"
            "- Escalate to human for complex requests\n"
            "- Cite listing IDs as [id: N] when mentioning listings\n"
            "- Answer in the user's language (French or English)\n"
        )

    @staticmethod
    def _looks_french(text: str) -> bool:
        """Detect if text is in French."""
        french_markers = ("louer", "vente", "appartement", "villa", "studio",
                          "riad", "marrakech", "casablanca", "cher", "bonjour",
                          "je veux", "je cherche", "merci", "s'il vous plaît")
        lowered = text.lower()
        return any(m in lowered for m in french_markers)

    def _build_tool_descriptions(self) -> str:
        """Build tool descriptions for the LLM."""
        lines = []
        for tool in self.tools.values():
            params = json.dumps(tool.parameters, ensure_ascii=False)
            lines.append(f"- {tool.name}: {tool.description}. Parameters: {params}")
        return "\n".join(lines)

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from LLM response. Expects JSON in ```tool_code``` blocks."""
        calls = []
        # Look for tool calls in code blocks marked as tool_code
        pattern = r"```tool_code\s*(\{.*?\})\s*```"
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                call = json.loads(match.strip())
                if "tool" in call and "args" in call:
                    calls.append(call)
            except json.JSONDecodeError:
                continue
        return calls

    def _execute_tool(self, tool_name: str, args: Dict[str, Any], user_id: Optional[int]) -> ToolResult:
        """Execute a tool with validation and logging."""
        if tool_name not in ALLOWED_TOOLS:
            result = ToolResult(success=False, error=f"Tool '{tool_name}' is not allowed")
            log_agent_action(user_id, "tool_blocked", tool_name, args, result)
            return result

        tool = self.tools.get(tool_name)
        if not tool:
            result = ToolResult(success=False, error=f"Tool '{tool_name}' not found")
            log_agent_action(user_id, "tool_error", tool_name, args, result)
            return result

        # Validate arguments
        try:
            validated_args = tool.validate_args(args)
        except ValueError as exc:
            result = ToolResult(success=False, error=f"Invalid arguments: {exc}")
            log_agent_action(user_id, "tool_validation_error", tool_name, args, result)
            return result

        # Human approval for booking
        if tool_name == "book_visit" and self.require_human_approval_for_booking:
            # In a real implementation, this would pause and wait for human approval
            # For now, we log and require the caller to handle approval
            result = ToolResult(
                success=False,
                error="HUMAN_APPROVAL_REQUIRED: Visit booking requires human confirmation",
            )
            log_agent_action(user_id, "tool_requires_approval", tool_name, validated_args, result)
            return result

        # Execute the tool
        result = tool.execute(validated_args, user_id)
        log_agent_action(user_id, "tool_executed", tool_name, validated_args, result)
        return result

    def run(
        self,
        user_message: str,
        user_id: Optional[int] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Run the agent for one user message."""
        # Input validation (guardrails)
        validation_error = validate_input(user_message)
        if validation_error:
            # Extract attack type from validation error
            attack_type = "unknown"
            if "detected " in validation_error:
                attack_type = validation_error.split("detected ")[1].split(".")[0]
            
            # Alert n8n
            alert_blocked_prompt(user_id, attack_type, user_message)
            
            log_agent_action(user_id, "input_blocked", "validation", {"message": user_message[:100]}, ToolResult(success=False, error=validation_error))
            return {
                "answer": f"Je ne peux pas traiter cette demande. {validation_error}."
                if self._looks_french(user_message)
                else f"I cannot process this request. {validation_error}.",
                "tool_calls": [],
                "iterations": 0,
                "blocked": True,
                "block_reason": validation_error,
            }

        # Redact PII from user message before sending to LLM
        safe_message = redact_pii(user_message)

        # Build conversation
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": safe_message})

        # Add tool descriptions
        tool_desc = self._build_tool_descriptions()
        messages.append({"role": "system", "content": f"Available tools:\n{tool_desc}"})

        iteration = 0
        tool_results: List[Dict[str, Any]] = []

        while iteration < self.max_iterations:
            iteration += 1

            # Format messages for LLM (simple concatenation for now)
            prompt = "\n\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in messages
            )

            # Get LLM response
            response = self.llm.generate(prompt)

            # Extract tool calls
            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                # No tool calls, return the response
                return {
                    "answer": response,
                    "tool_calls": tool_results,
                    "iterations": iteration,
                }

            # Execute tool calls
            for call in tool_calls:
                tool_name = call.get("tool")
                args = call.get("args", {})
                result = self._execute_tool(tool_name, args, user_id)
                tool_results.append({
                    "tool": tool_name,
                    "args": args,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                })

                # Add tool result to conversation
                if result.success:
                    result_text = json.dumps(result.data, ensure_ascii=False, default=str)
                else:
                    result_text = f"Error: {result.error}"
                messages.append({"role": "tool", "content": f"{tool_name}: {result_text}"})

        return {
            "answer": "Maximum iterations reached. Please try again or escalate to human.",
            "tool_calls": tool_results,
            "iterations": iteration,
        }


# ── Convenience function ──────────────────────────────────────────────────

def run_agent(
    user_message: str,
    user_id: Optional[int] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Run the agent with default settings."""
    agent = Agent()
    return agent.run(user_message, user_id, conversation_history)