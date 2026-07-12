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


