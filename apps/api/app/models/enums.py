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




