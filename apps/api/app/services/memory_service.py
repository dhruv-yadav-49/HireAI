import uuid
import re
import math
import json
from datetime import datetime, timedelta
from typing import Optional, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MemoryType, ConversationMemoryScope, AIProvider
from app.models.ai_memory import AIMemory
from app.models.ai_conversation import AIConversation
from app.models.ai_message import AIMessage
from app.models.ai_agent import AIProviderConfig, AIAgent
from app.services.llm_provider_registry import LLMProviderRegistry


class MemoryService:
    """Manages AI short-term/long-term memory records, time decays, and hybrid rule+LLM extraction pipelines."""

    @classmethod
    async def create_memory(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        content: str,
        scope: ConversationMemoryScope,
        memory_type: MemoryType,
        source: str,
        conversation_id: Optional[uuid.UUID] = None,
        lead_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        importance_score: float = 1.0,
        confidence_score: float = 1.0,
        supersedes_memory_id: Optional[uuid.UUID] = None
    ) -> AIMemory:
        memory = AIMemory(
            organization_id=org_id,
            conversation_id=conversation_id,
            lead_id=lead_id,
            user_id=user_id,
            scope=scope,
            memory_type=memory_type,
            content=content,
            importance_score=importance_score,
            confidence_score=confidence_score,
            source=source,
            supersedes_memory_id=supersedes_memory_id
        )
        db.add(memory)
        await db.flush()
        return memory

    @classmethod
    async def get_active_memories(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        lead_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        scope: Optional[ConversationMemoryScope] = None
    ) -> list[dict[str, Any]]:
        stmt = select(AIMemory).where(
            AIMemory.organization_id == org_id
        )
        if lead_id:
            stmt = stmt.where(AIMemory.lead_id == lead_id)
        if user_id:
            stmt = stmt.where(AIMemory.user_id == user_id)
        if scope:
            stmt = stmt.where(AIMemory.scope == scope)

        result = await db.execute(stmt)
        memories = list(result.scalars().all())
        
        # Calculate effective decay score dynamically:
        # effective_score = importance_score * confidence_score * exp(-0.01 * age_in_days)
        active_list = []
        now = datetime.utcnow()
        for m in memories:
            # Skip if memory is superseded by another version
            # (i.e. check if there exists another memory pointing to this one)
            superseded_stmt = select(AIMemory).where(AIMemory.supersedes_memory_id == m.id)
            is_superseded = (await db.execute(superseded_stmt)).scalar_one_or_none() is not None
            if is_superseded:
                continue

            age_days = (now - m.last_accessed_at.replace(tzinfo=None)).total_seconds() / 86400.0
            recency = math.exp(-0.02 * age_days)  # exponential decay constant lambda = 0.02
            effective_score = float(m.importance_score) * float(m.confidence_score) * recency
            
            # Touch last accessed timestamp to update recency
            m.last_accessed_at = now
            
            active_list.append({
                "id": m.id,
                "content": m.content,
                "scope": m.scope,
                "memory_type": m.memory_type,
                "importance_score": float(m.importance_score),
                "confidence_score": float(m.confidence_score),
                "effective_score": effective_score,
                "memory_version": m.memory_version,
                "source": m.source,
                "supersedes_memory_id": m.supersedes_memory_id
            })
            
        # Sort by decay score descending
        active_list.sort(key=lambda x: x["effective_score"], reverse=True)
        await db.commit()
        return active_list

    @classmethod
    async def extract_memories(cls, db: AsyncSession, conversation_id: uuid.UUID) -> list[AIMemory]:
        """Extracts customer facts/preferences using regex (Rule Extractor) and LLM-based parsing."""
        # Fetch conversation & messages
        conv = (await db.execute(select(AIConversation).where(AIConversation.id == conversation_id))).scalar_one_or_none()
        if not conv:
            return []

        messages_result = await db.execute(
            select(AIMessage).where(AIMessage.conversation_id == conversation_id).order_by(AIMessage.created_at.asc())
        )
        messages = list(messages_result.scalars().all())
        if not messages:
            return []

        dialogue_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
        extracted_memories = []

        # ── Step 1: Rule Extractor (Regex matches) ──
        # Check for budget matching
        budget_match = re.search(r"(?:budget(?:\s+is|\s+around)?\s*[:=]?\s*)\$?(\d+k?|\d+(?:,\d+)*)", dialogue_text, re.IGNORECASE)
        if budget_match:
            budget_val = budget_match.group(1)
            content = f"Lead mentioned a budget of {budget_val}"
            # Check if there is an existing budget memory for this lead to supersede
            supersedes_id = None
            if conv.lead_id:
                old_stmt = select(AIMemory).where(
                    AIMemory.lead_id == conv.lead_id,
                    AIMemory.content.ilike("%budget%")
                )
                old_mem = (await db.execute(old_stmt)).scalars().first()
                if old_mem:
                    supersedes_id = old_mem.id
            
            m = await cls.create_memory(
                db=db,
                org_id=conv.organization_id,
                content=content,
                scope=ConversationMemoryScope.LEAD,
                memory_type=MemoryType.FACT,
                source="RULE_EXTRACTOR",
                conversation_id=conversation_id,
                lead_id=conv.lead_id,
                user_id=conv.user_id,
                importance_score=0.9,
                confidence_score=1.0,
                supersedes_memory_id=supersedes_id
            )
            extracted_memories.append(m)

        # ── Step 2: LLM Extractor ──
        # Fetch active agent
        agent = (await db.execute(select(AIAgent).where(AIAgent.id == conv.agent_id))).scalar_one_or_none()
        if agent:
            # Instantiate LLM provider
            try:
                # Retrieve configuration credentials
                api_config = None
                if agent.provider_config_id:
                    api_config = (await db.execute(select(AIProviderConfig).where(AIProviderConfig.id == agent.provider_config_id))).scalar_one_or_none()
                
                credentials = {}
                if api_config:
                    credentials = api_config.credentials_json
                
                provider = LLMProviderRegistry.get_provider(agent.provider)
                system_instruction = (
                    "You are a background fact extractor. Analyze the conversation transcript "
                    "between the assistant and user/lead. Extract key facts, preferences, and details "
                    "about the user/lead (e.g. hiring needs, tech stack preferences, response style). "
                    "Do NOT duplicate rules-extracted info like exact budget numbers. "
                    "Return a JSON block containing a list of strings named 'memories'. "
                    "For example: {\"memories\": [\"Prefers emails for schedules\", \"Hiring a Senior Python engineer\"]}"
                )
                
                resp = await provider.generate(
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": dialogue_text}
                    ],
                    model=agent.model,
                    temperature=0.0,
                    credentials=credentials
                )
                
                content_str = resp.get("content") or ""
                # Attempt to parse json
                json_match = re.search(r"\{.*\}", content_str, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    facts = data.get("memories") or []
                    for fact in facts:
                        m = await cls.create_memory(
                            db=db,
                            org_id=conv.organization_id,
                            content=fact,
                            scope=ConversationMemoryScope.LEAD if conv.lead_id else ConversationMemoryScope.USER,
                            memory_type=MemoryType.PREFERENCE,
                            source="LLM_EXTRACTOR",
                            conversation_id=conversation_id,
                            lead_id=conv.lead_id,
                            user_id=conv.user_id,
                            importance_score=0.7,
                            confidence_score=0.8
                        )
                        extracted_memories.append(m)
            except Exception as e:
                # Log LLM extraction failures gracefully to not disrupt execution
                print(f"MemoryService LLM extraction failed: {str(e)}")
                
        await db.commit()
        return extracted_memories
