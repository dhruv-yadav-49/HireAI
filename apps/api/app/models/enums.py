from enum import Enum


class OrganizationRole(str, Enum):
    """Reused everywhere a role check is needed -- OrganizationMember,
    invitations, and future permission-engine work. Defined once here so
    no module ever redefines its own copy."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    SALES = "SALES"
    VIEWER = "VIEWER"


class OrganizationStatus(str, Enum):
    """Default is TRIAL, not ACTIVE -- every new org starts in a trial
    state until billing marks it ACTIVE. This column exists now so the
    future billing module doesn't need a schema change, just to start
    writing to it."""

    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"


class MemberStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class InvitationStatus(str, Enum):
    """Only the enum is used in Sprint 2A (the invitation model exists,
    but nothing writes PENDING/ACCEPTED transitions yet -- that logic
    lands in Sprint 2B with NotificationService and the accept flow)."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class LeadStatus(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    QUALIFIED = "QUALIFIED"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"
    ARCHIVED = "ARCHIVED"


class LeadPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class LeadSource(str, Enum):
    MANUAL = "MANUAL"
    CSV = "CSV"
    HUBSPOT = "HUBSPOT"
    ZOHO = "ZOHO"
    SALESFORCE = "SALESFORCE"
    WEBSITE = "WEBSITE"
    FACEBOOK = "FACEBOOK"
    GOOGLE = "GOOGLE"
    REFERRAL = "REFERRAL"
    LINKEDIN = "LINKEDIN"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    API = "API"
    OTHER = "OTHER"


class LeadActivityType(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    OWNER_CHANGED = "OWNER_CHANGED"
    ASSIGNED = "ASSIGNED"
    TAG_ADDED = "TAG_ADDED"
    TAG_REMOVED = "TAG_REMOVED"
    NOTE_ADDED = "NOTE_ADDED"


class ActorType(str, Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AI = "AI"
    WEBHOOK = "WEBHOOK"


class CreatedSource(str, Enum):
    MANUAL_UI = "MANUAL_UI"
    CSV_IMPORT = "CSV_IMPORT"
    API = "API"
    WEBHOOK = "WEBHOOK"
    AI_AGENT = "AI_AGENT"


class TaskStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskType(str, Enum):
    CALL = "CALL"
    EMAIL = "EMAIL"
    MEETING = "MEETING"
    FOLLOW_UP = "FOLLOW_UP"
    DEMO = "DEMO"
    PROPOSAL = "PROPOSAL"
    CUSTOM = "CUSTOM"


class TaskActivityType(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    REOPENED = "REOPENED"
    CANCELLED = "CANCELLED"


class WorkflowTriggerType(str, Enum):
    LEAD_CREATED = "LEAD_CREATED"
    LEAD_UPDATED = "LEAD_UPDATED"
    LEAD_STATUS_CHANGED = "LEAD_STATUS_CHANGED"
    TASK_CREATED = "TASK_CREATED"
    TASK_COMPLETED = "TASK_COMPLETED"
    LEAD_INACTIVE = "LEAD_INACTIVE"
    TASK_DUE_SOON = "TASK_DUE_SOON"
    MANUAL = "MANUAL"
    API = "API"
    # Reserved: DEAL_CREATED, EMAIL_RECEIVED, WEBHOOK, CALENDAR_EVENT


class ConditionOperator(str, Enum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    CONTAINS = "CONTAINS"
    STARTS_WITH = "STARTS_WITH"
    ENDS_WITH = "ENDS_WITH"
    IN = "IN"
    NOT_IN = "NOT_IN"
    IS_NULL = "IS_NULL"
    IS_NOT_NULL = "IS_NOT_NULL"


class ConditionValueType(str, Enum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    DATETIME = "DATETIME"


class WorkflowActionType(str, Enum):
    CREATE_TASK = "CREATE_TASK"
    UPDATE_LEAD = "UPDATE_LEAD"
    CHANGE_STATUS = "CHANGE_STATUS"
    ASSIGN_USER = "ASSIGN_USER"
    ADD_NOTE = "ADD_NOTE"
    ADD_TAG = "ADD_TAG"
    SEND_EMAIL = "SEND_EMAIL"
    SEND_WHATSAPP = "SEND_WHATSAPP"


class WorkflowExecutionStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class StepExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class JobStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"
    SYSTEM = "SYSTEM"


class JobType(str, Enum):
    GENERATE_REMINDERS = "GENERATE_REMINDERS"
    PROCESS_REMINDERS = "PROCESS_REMINDERS"
    SEND_QUEUED_NOTIFICATIONS = "SEND_QUEUED_NOTIFICATIONS"
    SYSTEM_PRUNE_LOGS = "SYSTEM_PRUNE_LOGS"


class JobExecutionStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class EntityType(str, Enum):
    LEAD = "LEAD"
    TASK = "TASK"


class ReminderType(str, Enum):
    INACTIVITY = "INACTIVITY"
    DUE_TASK = "DUE_TASK"
    FOLLOW_UP = "FOLLOW_UP"
    BIRTHDAY = "BIRTHDAY"


class ReminderStatus(str, Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    DISMISSED = "DISMISSED"
    FAILED = "FAILED"


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"


class RecipientType(str, Enum):
    USER = "USER"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    GROUP = "GROUP"
    LEAD = "LEAD"
    RAW = "RAW"


class NotificationPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class NotificationStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"


class NotificationProvider(str, Enum):
    SMTP = "SMTP"
    SES = "SES"
    SENDGRID = "SENDGRID"
    TWILIO = "TWILIO"
    META = "META"
    GUPSHUP = "GUPSHUP"


class CommunicationChannel(str, Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"


class CommunicationStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ProviderType(str, Enum):
    SMTP = "SMTP"
    GMAIL = "GMAIL"
    SES = "SES"
    META = "META"
    TWILIO = "TWILIO"
    MSG91 = "MSG91"
    MOCK = "MOCK"


class TemplateType(str, Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"


class CommunicationPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class CommunicationDirection(str, Enum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"


class DeliveryEvent(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"
    OPENED = "OPENED"
    CLICKED = "CLICKED"
    READ = "READ"
    DELIVERY_UNKNOWN = "DELIVERY_UNKNOWN"
    UNSUBSCRIBED = "UNSUBSCRIBED"
    SPAM_REPORTED = "SPAM_REPORTED"
    REJECTED = "REJECTED"


class AIProvider(str, Enum):
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GEMINI = "GEMINI"
    MOCK = "MOCK"


class MessageRole(str, Enum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


class ConversationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ToolExecutionStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AIRuntimeState(str, Enum):
    IDLE = "IDLE"
    PROMPT_BUILD = "PROMPT_BUILD"
    LLM_CALL = "LLM_CALL"
    WAITING_TOOL = "WAITING_TOOL"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    FINAL_RESPONSE = "FINAL_RESPONSE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EmbeddingProvider(str, Enum):
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    MOCK = "MOCK"


class EmbeddingStatus(str, Enum):
    PENDING = "PENDING"
    EMBEDDED = "EMBEDDED"
    FAILED = "FAILED"


class KnowledgeDocumentStatus(str, Enum):
    UPLOADING = "UPLOADING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class MemoryType(str, Enum):
    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    SEMANTIC = "SEMANTIC"
    FACT = "FACT"
    PREFERENCE = "PREFERENCE"


class ConversationMemoryScope(str, Enum):
    USER = "USER"
    LEAD = "LEAD"
    ORGANIZATION = "ORGANIZATION"
    GLOBAL = "GLOBAL"


class RetrievalSource(str, Enum):
    VECTOR = "VECTOR"
    CRM = "CRM"
    WORKFLOW = "WORKFLOW"
    DOCUMENT = "DOCUMENT"
    MEMORY = "MEMORY"
    HYBRID = "HYBRID"


class ChunkStrategy(str, Enum):
    FIXED = "FIXED"
    SLIDING = "SLIDING"
    MARKDOWN = "MARKDOWN"
    PARAGRAPH = "PARAGRAPH"
    SEMANTIC = "SEMANTIC"


class KnowledgeSourceType(str, Enum):
    UPLOAD = "UPLOAD"
    URL = "URL"
    CRM_EXPORT = "CRM_EXPORT"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    NOTION = "NOTION"
    CONFLUENCE = "CONFLUENCE"
    MANUAL = "MANUAL"


class PlannerState(str, Enum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AIActionType(str, Enum):
    ANALYZE_LEAD = "ANALYZE_LEAD"
    CREATE_TASK = "CREATE_TASK"
    SEND_EMAIL = "SEND_EMAIL"
    SEND_WHATSAPP = "SEND_WHATSAPP"
    UPDATE_LEAD = "UPDATE_LEAD"
    CHANGE_STATUS = "CHANGE_STATUS"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    WAIT = "WAIT"
    COMPLETE = "COMPLETE"


class AIActionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    WAITING_APPROVAL = "WAITING_APPROVAL"


class AIApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AgentType(str, Enum):
    SALES = "SALES"
    BUSINESS_ANALYST = "BUSINESS_ANALYST"
    MARKETING = "MARKETING"
    SUPPORT = "SUPPORT"
    RECRUITER = "RECRUITER"
    FINANCE = "FINANCE"
    HUMAN = "HUMAN"


class AgentTaskStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MessageType(str, Enum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    EVENT = "EVENT"
    HANDOFF = "HANDOFF"


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BackoffPolicy(str, Enum):
    FIXED = "FIXED"
    EXPONENTIAL = "EXPONENTIAL"
    NONE = "NONE"


class CollaborationMode(str, Enum):
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"
    CONDITIONAL = "CONDITIONAL"
    FAN_OUT = "FAN_OUT"
    FAN_IN = "FAN_IN"


class BusinessReportType(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    CUSTOM = "CUSTOM"


class ForecastPeriod(str, Enum):
    F_7_DAYS = "7_DAYS"
    F_30_DAYS = "30_DAYS"
    F_90_DAYS = "90_DAYS"
    F_180_DAYS = "180_DAYS"


class RecommendationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PipelineHealth(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RecommendationStatus(str, Enum):
    PENDING = "PENDING"
    DELEGATED = "DELEGATED"
    DISMISSED = "DISMISSED"


class TrendDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    STABLE = "STABLE"


class AnomalySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CampaignType(str, Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    MULTI_CHANNEL = "MULTI_CHANNEL"
    NEWSLETTER = "NEWSLETTER"
    REENGAGEMENT = "REENGAGEMENT"


class CampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class CampaignGoal(str, Enum):
    LEAD_GENERATION = "LEAD_GENERATION"
    LEAD_NURTURING = "LEAD_NURTURING"
    REENGAGEMENT = "REENGAGEMENT"
    PRODUCT_LAUNCH = "PRODUCT_LAUNCH"
    UPSELL = "UPSELL"
    CROSS_SELL = "CROSS_SELL"
    WEBINAR = "WEBINAR"
    EVENT = "EVENT"


class AudienceType(str, Enum):
    ALL_LEADS = "ALL_LEADS"
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    CUSTOM = "CUSTOM"
    INACTIVE = "INACTIVE"
    HIGH_VALUE = "HIGH_VALUE"


class ContentType(str, Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    SOCIAL = "SOCIAL"
    LANDING_PAGE = "LANDING_PAGE"


class ABTestStatus(str, Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"




class CampaignPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ── Sprint 6A: AI Observability Platform ──────────────────────────────────────

class TraceStatus(str, Enum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TraceType(str, Enum):
    EXECUTION = "EXECUTION"
    PROMPT = "PROMPT"
    RETRIEVAL = "RETRIEVAL"
    PLANNING = "PLANNING"
    REASONING = "REASONING"
    POLICY = "POLICY"
    TOOL = "TOOL"


class MetricType(str, Enum):
    LATENCY = "LATENCY"
    TOKEN = "TOKEN"
    COST = "COST"
    MEMORY = "MEMORY"
    RETRIEVAL = "RETRIEVAL"
    TOOL = "TOOL"
    PLANNING = "PLANNING"
    POLICY = "POLICY"


class TraceSamplingMode(str, Enum):
    FULL = "FULL"        # Record every trace
    HEAD = "HEAD"        # Record first N per session
    DISABLED = "DISABLED"  # No tracing


# ── Sprint 6B: AI Evaluation Framework ────────────────────────────────────────

class EvaluationStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvaluationMetric(str, Enum):
    GROUNDING = "GROUNDING"
    RETRIEVAL = "RETRIEVAL"
    PLANNING = "PLANNING"
    REASONING = "REASONING"
    TOOLS = "TOOLS"
    POLICY = "POLICY"
    LATENCY = "LATENCY"
    COST = "COST"
    HALLUCINATION = "HALLUCINATION"
    OVERALL = "OVERALL"


class QualityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class FeedbackType(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


class FeedbackCategory(str, Enum):
    WRONG_ANSWER = "WRONG_ANSWER"
    TOO_SLOW = "TOO_SLOW"
    INCORRECT_TOOL = "INCORRECT_TOOL"
    HALLUCINATION = "HALLUCINATION"
    OTHER = "OTHER"


class QualityRuleAction(str, Enum):
    WARN = "WARN"
    FAIL = "FAIL"
    BLOCK = "BLOCK"
    NOTIFY = "NOTIFY"


# ── Sprint 6C: Human Feedback & Continuous Learning ──────────────────────────

class LearningStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ImprovementType(str, Enum):
    PROMPT = "PROMPT"
    PLANNER = "PLANNER"
    RETRIEVAL = "RETRIEVAL"
    POLICY = "POLICY"
    TOOL = "TOOL"
    MEMORY = "MEMORY"


class SuggestionStatus(str, Enum):
    NEW = "NEW"
    ANALYZED = "ANALYZED"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    DEPLOYED = "DEPLOYED"
    REJECTED = "REJECTED"


class LearningTriggerMode(str, Enum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    EVENT_DRIVEN = "EVENT_DRIVEN"


# ── Sprint 7A: Distributed Execution Platform ───────────────────────────────

class AIJobStatus(str, Enum):
    QUEUED = "QUEUED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"
    DEAD_LETTER = "DEAD_LETTER"


class WorkerStatus(str, Enum):
    STARTING = "STARTING"
    IDLE = "IDLE"
    BUSY = "BUSY"
    DRAINING = "DRAINING"
    OFFLINE = "OFFLINE"


class QueueType(str, Enum):
    DEFAULT = "DEFAULT"
    PRIORITY = "PRIORITY"
    LONG_RUNNING = "LONG_RUNNING"
    RETRY = "RETRY"
    DEAD_LETTER = "DEAD_LETTER"
    SALES = "SALES"
    MARKETING = "MARKETING"
    ANALYTICS = "ANALYTICS"


class RetryStrategy(str, Enum):
    NONE = "NONE"
    FIXED_DELAY = "FIXED_DELAY"
    EXPONENTIAL_BACKOFF = "EXPONENTIAL_BACKOFF"
    JITTER = "JITTER"


class JobFailureCategory(str, Enum):
    LLM_ERROR = "LLM_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    TIMEOUT = "TIMEOUT"
    VALIDATION = "VALIDATION"
    SYSTEM = "SYSTEM"


# ── Sprint 7B: Enterprise Event Bus Platform ─────────────────────────────────

class EventStatus(str, Enum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    DEAD_LETTER = "DEAD_LETTER"


class EventType(str, Enum):
    JOB_CREATED = "JOB_CREATED"
    JOB_STARTED = "JOB_STARTED"
    JOB_COMPLETED = "JOB_COMPLETED"
    TRACE_CREATED = "TRACE_CREATED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    LEARNING_DATASET_CREATED = "LEARNING_DATASET_CREATED"
    LEARNING_SUGGESTION_CREATED = "LEARNING_SUGGESTION_CREATED"
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    CAMPAIGN_STARTED = "CAMPAIGN_STARTED"
    CAMPAIGN_COMPLETED = "CAMPAIGN_COMPLETED"


class SubscriberStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"


# ── Sprint 7C: Enterprise Security Platform ───────────────────────────────────

class APIKeyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    EXECUTE = "EXECUTE"
    APPROVE = "APPROVE"
    REVOKE = "REVOKE"
    ROTATE = "ROTATE"
    DENIED = "DENIED"


class SecretType(str, Enum):
    API_KEY = "API_KEY"
    PASSWORD = "PASSWORD"
    TOKEN = "TOKEN"
    CERTIFICATE = "CERTIFICATE"


class PIIType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    CREDIT_CARD = "CREDIT_CARD"


class SecurityPolicyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class AuthMethod(str, Enum):
    JWT = "JWT"
    API_KEY = "API_KEY"
    OAUTH = "OAUTH"
    OIDC = "OIDC"
    SAML = "SAML"


# ── Sprint 7D: AI Governance Platform ─────────────────────────────────────────

class GovernanceDecisionStatus(str, Enum):
    """Final decision produced by the Governance Engine."""
    PERMIT = "PERMIT"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    PENDING = "PENDING"          # decision is being computed (async path)


class GovernanceApprovalStatus(str, Enum):
    """Lifecycle status of a human approval request."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    AUTO_APPROVED = "AUTO_APPROVED"


class RiskLevel(str, Enum):
    """Qualitative risk band derived from the numeric risk score."""
    CRITICAL = "CRITICAL"    # score >= 0.90
    HIGH = "HIGH"            # score >= 0.70
    MEDIUM = "MEDIUM"        # score >= 0.50
    LOW = "LOW"              # score >= 0.30
    NEGLIGIBLE = "NEGLIGIBLE"  # score < 0.30


class PolicyPackType(str, Enum):
    """Named governance policy pack."""
    DEFAULT = "DEFAULT"
    SOC2 = "SOC2"
    GDPR = "GDPR"
    HIPAA = "HIPAA"
    CUSTOM = "CUSTOM"


class ComplianceFramework(str, Enum):
    """External compliance frameworks for reporting."""
    OWASP_ASVS = "OWASP_ASVS"
    OWASP_TOP10 = "OWASP_TOP10"
    SOC2 = "SOC2"
    ISO_27001 = "ISO_27001"
    GDPR = "GDPR"
    HIPAA = "HIPAA"


class ViolationSeverity(str, Enum):
    """Severity of a detected policy violation."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


# ── Sprint 7E: AI Playground Platform ─────────────────────────────────────────

class PlaygroundSessionStatus(str, Enum):
    """Lifecycle status of a playground session (CTO #11)."""
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


class ExperimentStatus(str, Enum):
    """Execution status of a playground experiment or matrix run."""
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ComparisonType(str, Enum):
    """Type of side-by-side comparison matrix."""
    PROMPT = "PROMPT"
    MODEL = "MODEL"
    RUNTIME = "RUNTIME"
    GOVERNANCE = "GOVERNANCE"


class SandboxIsolationLevel(str, Enum):
    """Isolation mode for sandbox runtime (CTO #2)."""
    READ_ONLY = "READ_ONLY"
    READ_WITH_CACHE = "READ_WITH_CACHE"
    MOCK_EXTERNALS = "MOCK_EXTERNALS"


# ── Sprint 8A: Agent Marketplace Platform ─────────────────────────────────────

class AgentLifecycleStatus(str, Enum):
    """Formal lifecycle state machine for agent packages (CTO #5)."""
    DRAFT = "DRAFT"
    SANDBOX_TESTED = "SANDBOX_TESTED"
    SECURITY_CHECKED = "SECURITY_CHECKED"
    GOVERNANCE_CHECKED = "GOVERNANCE_CHECKED"
    PUBLISHED = "PUBLISHED"
    INSTALLED = "INSTALLED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


class AgentInstallationStatus(str, Enum):
    """Installation status per organization tenant (CTO #7)."""
    PENDING = "PENDING"
    INSTALLED = "INSTALLED"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    UNINSTALLED = "UNINSTALLED"


class AgentPackageType(str, Enum):
    """Classification of marketplace agent packages."""
    SYSTEM = "SYSTEM"
    COMMUNITY = "COMMUNITY"
    ENTERPRISE = "ENTERPRISE"
    CUSTOM = "CUSTOM"


# ── Sprint 8B: Marketplace Experience & Resolver ──────────────────────────────

class ReleaseChannel(str, Enum):
    """Release channels for version management (CTO #4)."""
    STABLE = "STABLE"
    BETA = "BETA"
    NIGHTLY = "NIGHTLY"
    DEPRECATED = "DEPRECATED"


class PublisherVerificationBadge(str, Enum):
    """Trust and verification badges for publisher profiles (CTO #7)."""
    OFFICIAL = "OFFICIAL"
    VERIFIED_PARTNER = "VERIFIED_PARTNER"
    COMMUNITY_CONTRIBUTOR = "COMMUNITY_CONTRIBUTOR"


class PublishingStage(str, Enum):
    """Extended publishing workflow stages (CTO #4)."""
    DRAFT = "DRAFT"
    VALIDATION = "VALIDATION"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


# ── Sprint 10: Commercial Cloud Operations & Scale ─────────────────────────────

class SubscriptionPlan(str, Enum):
    """Commercial tier subscription plans (CTO #4)."""
    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class MeteredMetricType(str, Enum):
    """Generic usage metering event types (CTO #2)."""
    AI_TOKEN = "AI_TOKEN"
    API_CALL = "API_CALL"
    AGENT_TASK = "AGENT_TASK"
    LLM_COST = "LLM_COST"
    WORKFLOW_EXECUTION = "WORKFLOW_EXECUTION"
    TOOL_INVOCATION = "TOOL_INVOCATION"
    PLAYGROUND_SESSION = "PLAYGROUND_SESSION"
    MARKETPLACE_DOWNLOAD = "MARKETPLACE_DOWNLOAD"
    STORAGE_MB = "STORAGE_MB"


class EntitlementFeature(str, Enum):
    """Entitlement feature gates separated from subscription plans (CTO #4)."""
    CUSTOM_AGENTS = "CUSTOM_AGENTS"
    GOVERNANCE_APPROVALS = "GOVERNANCE_APPROVALS"
    PLAYGROUND_MATRIX = "PLAYGROUND_MATRIX"
    MARKETPLACE_PUBLISHING = "MARKETPLACE_PUBLISHING"
    UNLIMITED_TOKENS = "UNLIMITED_TOKENS"

