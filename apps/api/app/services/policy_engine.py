import uuid
from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.context import RequestContext
from app.models.enums import AIActionType
from app.models.communication import Communication


class PolicyDecision:
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class AIPolicyEngine:
    @classmethod
    async def evaluate(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        agent_type: str,
        action_type: AIActionType,
        tool_name: Optional[str],
        input_json: dict,
        plan_id: uuid.UUID
    ) -> dict:
        """
        Evaluates an action against tenant policies, tool restrictions, and risk level.
        Returns:
            {
                "decision": "ALLOW" | "REQUIRE_APPROVAL" | "DENY",
                "policy": str,
                "risk": "LOW" | "MEDIUM" | "HIGH",
                "reason": str
            }
        """
        # 1. Verify Tool Permissions (Agent boundary)
        allowed_tools = {
            "SALES": ["LeadTool", "TaskTool", "CommunicationTool"],
            "SUPPORT": ["CommunicationTool", "TaskTool"],
            "RECRUITER": ["LeadTool", "CommunicationTool", "TaskTool"]
        }
        
        if tool_name and tool_name not in allowed_tools.get(agent_type.upper(), []):
            return {
                "decision": PolicyDecision.DENY,
                "policy": "ToolPermissionPolicy",
                "risk": "HIGH",
                "reason": f"Agent type '{agent_type}' is not permitted to execute tool '{tool_name}'."
            }

        # 2. Check Communication Rate Limits (e.g. max 10 emails/WhatsApp messages per tenant per hour)
        if action_type in (AIActionType.SEND_EMAIL, AIActionType.SEND_WHATSAPP):
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            stmt = select(func.count(Communication.id)).where(
                Communication.organization_id == ctx.tenant_id,
                Communication.created_at >= one_hour_ago
            )
            res = await db.execute(stmt)
            count = res.scalar() or 0
            if count >= 10:
                return {
                    "decision": PolicyDecision.DENY,
                    "policy": "CommunicationLimitPolicy",
                    "risk": "HIGH",
                    "reason": f"Hourly communication rate limit of 10 reached for this tenant."
                }

        # 3. Check Keyword and Lead Value Criteria Approval Rules
        content_to_check = ""
        is_bulk = input_json.get("is_bulk", False)
        recipient_count = len(input_json.get("recipients", [])) or 1

        if action_type == AIActionType.SEND_EMAIL:
            content_to_check = (input_json.get("body", "") + " " + input_json.get("subject", "")).lower()
        elif action_type == AIActionType.SEND_WHATSAPP:
            content_to_check = input_json.get("body", "").lower()
        elif action_type == AIActionType.CREATE_TASK:
            content_to_check = (input_json.get("title", "") + " " + input_json.get("description", "")).lower()
        elif action_type == AIActionType.UPDATE_LEAD:
            content_to_check = str(input_json.get("lead_data", {})).lower()

        # Sensitive Keywords
        sensitive_keywords = ["discount", "contract", "delete", "refund", "cancel"]
        matched_kws = [kw for kw in sensitive_keywords if kw in content_to_check]
        if matched_kws:
            return {
                "decision": PolicyDecision.REQUIRE_APPROVAL,
                "policy": "KeywordApprovalPolicy",
                "risk": "HIGH",
                "reason": f"Action contains sensitive keyword: '{matched_kws[0]}'."
            }

        if is_bulk or recipient_count > 10:
            return {
                "decision": PolicyDecision.REQUIRE_APPROVAL,
                "policy": "BulkEmailPolicy",
                "risk": "HIGH",
                "reason": f"Recipient count ({recipient_count}) or bulk flag triggers approval rule."
            }

        # Check Lead Value (High-value leads > $10,000 require manual approval for modifications)
        lead_id = input_json.get("lead_id")
        if lead_id:
            try:
                from app.models.lead import Lead
                lead = await db.get(Lead, uuid.UUID(str(lead_id)))
                if lead and lead.estimated_value and lead.estimated_value > 10000:
                    if action_type in (AIActionType.SEND_EMAIL, AIActionType.SEND_WHATSAPP, AIActionType.UPDATE_LEAD):
                        return {
                            "decision": PolicyDecision.REQUIRE_APPROVAL,
                            "policy": "HighValueLeadPolicy",
                            "risk": "MEDIUM",
                            "reason": f"Actions involving high-value lead (estimated value ${lead.estimated_value}) require approval."
                        }
            except Exception:
                pass

        # 4. Prevent Unsafe Action Sequences (Consecutive Communications without Wait)
        from app.models.ai_action import AIAction
        stmt = select(AIAction).where(AIAction.plan_id == plan_id).order_by(AIAction.created_at.desc())
        res = await db.execute(stmt)
        past_actions = res.scalars().all()
        if past_actions and action_type in (AIActionType.SEND_EMAIL, AIActionType.SEND_WHATSAPP):
            last_action = past_actions[0]
            if last_action.action_type in (AIActionType.SEND_EMAIL, AIActionType.SEND_WHATSAPP) and last_action.status == "SUCCESS":
                return {
                    "decision": PolicyDecision.REQUIRE_APPROVAL,
                    "policy": "SequenceCheckPolicy",
                    "risk": "MEDIUM",
                    "reason": "Consecutive external communications without wait action require manual approval."
                }

        # 5. Default Risk Mapping
        # Low risk
        if action_type in (AIActionType.ANALYZE_LEAD, AIActionType.CHANGE_STATUS, AIActionType.WAIT, AIActionType.COMPLETE):
            return {
                "decision": PolicyDecision.ALLOW,
                "policy": "DefaultLowRiskPolicy",
                "risk": "LOW",
                "reason": "Action approved automatically."
            }

        # High risk default (external message sending requires human check by default)
        if action_type in (AIActionType.SEND_EMAIL, AIActionType.SEND_WHATSAPP):
            return {
                "decision": PolicyDecision.REQUIRE_APPROVAL,
                "policy": "DefaultExternalCommPolicy",
                "risk": "HIGH",
                "reason": f"External communication via {action_type.value} requires human approval."
            }

        return {
            "decision": PolicyDecision.ALLOW,
            "policy": "DefaultAllowPolicy",
            "risk": "LOW",
            "reason": "Action allowed."
        }
