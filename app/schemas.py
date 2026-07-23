from datetime import datetime

from pydantic import AliasPath, BaseModel, ConfigDict, EmailStr, Field

from app.models import ActorType, TicketCategory, TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: EmailStr
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=10000)
    priority: TicketPriority = TicketPriority.MEDIUM
    category: TicketCategory


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    actor: str = Field(
        default="agent:api",
        min_length=3,
        max_length=120,
        description="Stable agent reference. Authentication would supply this in production.",
    )


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    name: str = Field(validation_alias=AliasPath("actor", "display_name"))


class ActorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_type: ActorType
    display_name: str


class TicketEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    from_status: TicketStatus | None
    to_status: TicketStatus | None
    actor: ActorResponse
    metadata_json: str | None
    created_at: datetime


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer: CustomerResponse
    subject: str
    description: str
    priority: TicketPriority
    category: TicketCategory
    status: TicketStatus
    processing_summary: str | None
    assigned_department: str | None
    spam_score: int | None
    created_at: datetime
    updated_at: datetime


class TicketDetailResponse(TicketResponse):
    events: list[TicketEventResponse]


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    page: int
    page_size: int
    total: int


class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: str
    details: list[dict[str, object]] | None = None
