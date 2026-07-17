from app.models.enums import AIActionType


class StrategyRule:
    def __init__(self, stage: str, strategy: str, allowed_actions: list[AIActionType]):
        self.stage = stage
        self.strategy = strategy
        self.allowed_actions = allowed_actions


class SalesStrategyEngine:
    RULES = {
        "NEW": StrategyRule("NEW", "Introduction", [
            AIActionType.SEND_EMAIL,
            AIActionType.CREATE_TASK,
            AIActionType.ANALYZE_LEAD,
            AIActionType.WAIT
        ]),
        "CONTACTED": StrategyRule("CONTACTED", "Discovery", [
            AIActionType.SEND_EMAIL,
            AIActionType.SEND_WHATSAPP,
            AIActionType.CREATE_TASK,
            AIActionType.ANALYZE_LEAD,
            AIActionType.WAIT
        ]),
        "MEETING_SCHEDULED": StrategyRule("MEETING_SCHEDULED", "Discovery", [
            AIActionType.SEND_EMAIL,
            AIActionType.SEND_WHATSAPP,
            AIActionType.CREATE_TASK,
            AIActionType.ANALYZE_LEAD,
            AIActionType.WAIT
        ]),
        "QUALIFIED": StrategyRule("QUALIFIED", "Demo", [
            AIActionType.SEND_EMAIL,
            AIActionType.SEND_WHATSAPP,
            AIActionType.CREATE_TASK,
            AIActionType.ANALYZE_LEAD,
            AIActionType.WAIT
        ]),
        "PROPOSAL_SENT": StrategyRule("PROPOSAL_SENT", "Proposal", [
            AIActionType.SEND_EMAIL,
            AIActionType.SEND_WHATSAPP,
            AIActionType.CREATE_TASK,
            AIActionType.ANALYZE_LEAD,
            AIActionType.WAIT
        ]),
        "NEGOTIATION": StrategyRule("NEGOTIATION", "Proposal", [
            AIActionType.SEND_EMAIL,
            AIActionType.SEND_WHATSAPP,
            AIActionType.CREATE_TASK,
            AIActionType.ANALYZE_LEAD,
            AIActionType.WAIT
        ]),
        "WON": StrategyRule("WON", "Onboarding", [
            AIActionType.SEND_EMAIL,
            AIActionType.CREATE_TASK,
            AIActionType.ANALYZE_LEAD,
            AIActionType.WAIT
        ]),
        "LOST": StrategyRule("LOST", "Archive", [
            AIActionType.CREATE_TASK,
            AIActionType.ANALYZE_LEAD,
            AIActionType.WAIT
        ]),
        "ARCHIVED": StrategyRule("ARCHIVED", "Archive", [
            AIActionType.ANALYZE_LEAD
        ])
    }

    @classmethod
    def get_strategy_rule(cls, status: str) -> StrategyRule:
        status_upper = status.upper() if isinstance(status, str) else ""
        return cls.RULES.get(
            status_upper,
            StrategyRule(status_upper, "Introduction", [
                AIActionType.SEND_EMAIL,
                AIActionType.CREATE_TASK,
                AIActionType.ANALYZE_LEAD,
                AIActionType.WAIT
            ])
        )
