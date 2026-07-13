import tiktoken
from typing import Any, Optional
from app.services.retrieval_service import RetrievalResult
from app.models.enums import RetrievalSource


class ContextBuilder:
    """Enterprise Prompt Budget Manager dynamically constructing structured context within strict token budgets."""

    @classmethod
    def compile_prompt(
        cls,
        system_instruction: str,
        retrieved_results: list[RetrievalResult],
        conversation_history: list[dict[str, str]],
        current_message: str,
        max_total_tokens: int = 8000
    ) -> str:
        encoding = tiktoken.get_encoding("cl100k_base")

        # Define Budgets
        system_budget = 1000
        memories_budget = 1000
        knowledge_budget = 2500
        crm_budget = 1000
        conversation_budget = 2000
        
        # 1. System Prompt
        sys_tokens = encoding.encode(system_instruction)
        if len(sys_tokens) > system_budget:
            system_instruction = encoding.decode(sys_tokens[:system_budget])
        
        # Segment retrieved resources
        org_memories = []
        user_memories = []
        lead_memories = []
        knowledge_chunks = []
        crm_records = []

        for r in retrieved_results:
            if r.source == RetrievalSource.MEMORY:
                meta = r.metadata or {}
                scope = meta.get("scope") or "ORGANIZATION"
                if scope == "ORGANIZATION":
                    org_memories.append(r.content)
                elif scope == "USER":
                    user_memories.append(r.content)
                else:
                    lead_memories.append(r.content)
            elif r.source == RetrievalSource.VECTOR:
                knowledge_chunks.append(r.content)
            elif r.source == RetrievalSource.CRM:
                crm_records.append(r.content)

        # 2. Organization Memories
        org_mem_str = "\n".join(org_memories[:5])
        org_tokens = encoding.encode(org_mem_str)
        if len(org_tokens) > (memories_budget // 3):
            org_mem_str = encoding.decode(org_tokens[:(memories_budget // 3)])

        # 3. User Memories
        user_mem_str = "\n".join(user_memories[:5])
        user_tokens = encoding.encode(user_mem_str)
        if len(user_tokens) > (memories_budget // 3):
            user_mem_str = encoding.decode(user_tokens[:(memories_budget // 3)])

        # 4. Lead Memories
        lead_mem_str = "\n".join(lead_memories[:10])
        lead_tokens = encoding.encode(lead_mem_str)
        if len(lead_tokens) > (memories_budget // 3):
            lead_mem_str = encoding.decode(lead_tokens[:(memories_budget // 3)])

        # 5. Knowledge Documents
        knowledge_str = ""
        current_k_tokens = 0
        for chunk in knowledge_chunks[:8]:
            chunk_tokens = len(encoding.encode(chunk))
            if current_k_tokens + chunk_tokens <= knowledge_budget:
                knowledge_str += f"\n- {chunk}"
                current_k_tokens += chunk_tokens
            else:
                break

        # 6. CRM Records
        crm_str = ""
        current_crm_tokens = 0
        for rec in crm_records[:5]:
            rec_tokens = len(encoding.encode(rec))
            if current_crm_tokens + rec_tokens <= crm_budget:
                crm_str += f"\n- {rec}"
                current_crm_tokens += rec_tokens
            else:
                break

        # 7. Recent Conversations (sliding window from end)
        history_str = ""
        current_conv_tokens = 0
        # Iterate backwards to keep recent messages
        valid_history = []
        for msg in reversed(conversation_history[-20:]):
            msg_line = f"{msg['role']}: {msg['content']}"
            msg_tokens = len(encoding.encode(msg_line))
            if current_conv_tokens + msg_tokens <= conversation_budget:
                valid_history.append(msg_line)
                current_conv_tokens += msg_tokens
            else:
                break
        history_str = "\n".join(reversed(valid_history))

        # Assemble Prompt Context in exact order
        prompt_parts = []
        prompt_parts.append("=== SYSTEM INSTRUCTION ===")
        prompt_parts.append(system_instruction)
        
        if org_mem_str:
            prompt_parts.append("=== ORGANIZATION MEMORIES ===")
            prompt_parts.append(org_mem_str)
            
        if user_mem_str:
            prompt_parts.append("=== USER MEMORIES ===")
            prompt_parts.append(user_mem_str)

        if lead_mem_str:
            prompt_parts.append("=== LEAD MEMORIES ===")
            prompt_parts.append(lead_mem_str)

        if knowledge_str:
            prompt_parts.append("=== KNOWLEDGE CHUNKS ===")
            prompt_parts.append(knowledge_str.strip())

        if crm_str:
            prompt_parts.append("=== CRM CONTEXT ===")
            prompt_parts.append(crm_str.strip())

        if history_str:
            prompt_parts.append("=== RECENT CONVERSATION ===")
            prompt_parts.append(history_str)

        prompt_parts.append("=== CURRENT USER MESSAGE ===")
        prompt_parts.append(current_message)

        return "\n\n".join(prompt_parts)
