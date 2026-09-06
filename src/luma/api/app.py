from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import func, select

from luma.agents.tool_executor import TOOL_REGISTRY
from luma.api.dependencies import (
    BearerDependency,
    OperationsAccountDependency,
    SessionDependency,
)
from luma.api.schemas import (
    AccountResponse,
    ActionDecisionRequest,
    ActionDetailResponse,
    ActionIntentResponse,
    ApprovalDetailResponse,
    ApprovalResponse,
    CaseCreateRequest,
    CaseDetailResponse,
    CaseEventResponse,
    CaseResponse,
    CaseRunResponse,
    CustomerCommunicationResponse,
    CustomerEmailDraftRequest,
    EscalationResponse,
    EvidenceResponse,
    ExecutionAttemptResponse,
    InvestigationNoteRequest,
    InvestigationResolutionRequest,
    InvestigationUpdateResponse,
    LoginRequest,
    LoginResponse,
    OperationsCaseResponse,
    OperationsCaseWorkspaceResponse,
    OperationsOverviewResponse,
    OperationsResearchRequest,
    OperationsResearchResponse,
    PolicyRetrievalResponse,
    PolicySearchResultResponse,
    ProposalResponse,
    RecommendationPresentationResponse,
    VerificationResponse,
    WorkflowStageResponse,
)
from luma.config import Settings, get_settings
from luma.db.models.case_management import ActionIntent, CaseEvent, SupportCase
from luma.db.session import Database
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.retrieval.policy import search_policy
from luma.services.actions import ActionValidationError, decide_action
from luma.services.auth import create_session, revoke_session
from luma.services.cases import (
    CaseIntakeError,
    CreateCaseCommand,
    IdempotencyConflictError,
    create_case,
)
from luma.services.communications import (
    CommunicationWorkflowError,
    mock_send_final_email,
    update_final_email_draft,
)
from luma.services.investigations import (
    InvestigationWorkflowError,
    acknowledge_investigation,
    add_investigation_note,
    resolve_investigation,
)
from luma.services.operations import (
    get_operations_case_workspace,
    list_operations_cases,
    operations_overview,
)
from luma.services.recommendations import build_recommendation_presentation
from luma.tools.contracts import PolicySearchInput
from luma.tools.errors import EntityNotFoundError, EntityOwnershipError, ToolError


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(
            runtime_settings.database_url,
            echo=runtime_settings.database_echo,
        )
        app.state.database = database
        try:
            yield
        finally:
            await database.dispose()

    app = FastAPI(
        title="Luma Case Resolution API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/login", response_model=LoginResponse)
    async def login(payload: LoginRequest, session: SessionDependency) -> LoginResponse:
        ttl = timedelta(hours=runtime_settings.session_ttl_hours)
        async with session.begin():
            token = await create_session(
                session,
                username=payload.username,
                password=payload.password,
                ttl=ttl,
            )
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
            )
        return LoginResponse(access_token=token, expires_in_seconds=int(ttl.total_seconds()))

    @app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(
        credentials: BearerDependency,
        _: OperationsAccountDependency,
        session: SessionDependency,
    ) -> Response:
        assert credentials is not None
        async with session.begin():
            await revoke_session(session, credentials.credentials)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/api/auth/me", response_model=AccountResponse)
    async def current_account(account: OperationsAccountDependency) -> AccountResponse:
        return AccountResponse.model_validate(account)

    @app.post("/api/cases", response_model=CaseResponse)
    async def submit_case(
        payload: CaseCreateRequest,
        response: Response,
        session: SessionDependency,
    ) -> CaseResponse:
        try:
            async with session.begin():
                result = await create_case(
                    session,
                    CreateCaseCommand(
                        complaint_text=payload.complaint_text,
                        source=payload.source,
                        external_request_key=payload.external_request_key,
                        claimed_customer_reference=payload.claimed_customer_reference,
                        contact_email=payload.contact_email,
                        claimed_category=payload.claimed_category,
                    ),
                )
        except IdempotencyConflictError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        except CaseIntakeError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        return CaseResponse.model_validate(result.case).model_copy(
            update={"created": result.created}
        )

    @app.get("/api/cases", response_model=list[CaseResponse])
    async def list_cases(
        _: OperationsAccountDependency,
        session: SessionDependency,
        limit: int = 50,
    ) -> list[CaseResponse]:
        bounded_limit = max(1, min(limit, 200))
        cases = (
            await session.execute(
                select(SupportCase).order_by(SupportCase.received_at.desc()).limit(bounded_limit)
            )
        ).scalars()
        return [CaseResponse.model_validate(case_record) for case_record in cases]

    @app.get("/api/cases/{case_reference}", response_model=CaseDetailResponse)
    async def get_case(
        case_reference: str,
        _: OperationsAccountDependency,
        session: SessionDependency,
    ) -> CaseDetailResponse:
        case_record = await session.scalar(
            select(SupportCase).where(SupportCase.public_reference == case_reference)
        )
        if case_record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        events = (
            await session.execute(
                select(CaseEvent)
                .where(CaseEvent.case_id == case_record.id)
                .order_by(CaseEvent.sequence)
            )
        ).scalars()
        base = CaseResponse.model_validate(case_record).model_dump()
        return CaseDetailResponse(
            **base,
            events=[CaseEventResponse.model_validate(event) for event in events],
        )

    @app.get("/api/operations/overview", response_model=OperationsOverviewResponse)
    async def get_operations_overview(
        _: OperationsAccountDependency,
        session: SessionDependency,
    ) -> OperationsOverviewResponse:
        return OperationsOverviewResponse.model_validate(await operations_overview(session))

    @app.get("/api/operations/events")
    async def stream_operations_events(
        request: Request,
        _: OperationsAccountDependency,
    ) -> StreamingResponse:
        """Emit invalidation signals; clients refetch authoritative read models."""

        async def event_stream() -> AsyncIterator[str]:
            previous: tuple[object, ...] | None = None
            heartbeat = 0
            while not await request.is_disconnected():
                async with request.app.state.database.session() as stream_session:
                    fingerprint = (
                        await stream_session.execute(
                            select(
                                func.count(SupportCase.id),
                                func.max(SupportCase.updated_at),
                                func.coalesce(func.sum(SupportCase.version), 0),
                            ).where(~SupportCase.external_request_key.startswith("eval:"))
                        )
                    ).one()
                current = tuple(fingerprint)
                if current != previous:
                    payload = json.dumps(
                        {
                            "case_count": current[0],
                            "changed_at": None if current[1] is None else str(current[1]),
                            "version_sum": current[2],
                        }
                    )
                    yield f"event: cases_changed\ndata: {payload}\n\n"
                    previous = current
                    heartbeat = 0
                else:
                    heartbeat += 1
                    if heartbeat >= 15:
                        yield ": keep-alive\n\n"
                        heartbeat = 0
                await asyncio.sleep(1)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/operations/cases", response_model=list[OperationsCaseResponse])
    async def get_operations_cases(
        _: OperationsAccountDependency,
        session: SessionDependency,
        status_filter: str | None = Query(default=None, alias="status"),
        source: str | None = None,
        category: str | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OperationsCaseResponse]:
        rows = await list_operations_cases(
            session,
            status=status_filter,
            source=source,
            category=category,
            query=query,
            limit=limit,
            offset=offset,
        )
        return [
            OperationsCaseResponse(
                **CaseResponse.model_validate(row.case).model_dump(),
                category=row.category,
                outcome=row.outcome,
                disposition=row.disposition,
                escalation_reason=row.escalation_reason,
            )
            for row in rows
        ]

    @app.get(
        "/api/operations/policies/search",
        response_model=list[PolicySearchResultResponse],
    )
    async def search_operations_policies(
        _: OperationsAccountDependency,
        session: SessionDependency,
        query: str = Query(min_length=2, max_length=500),
        effective_on: date | None = None,
        policy_area: str | None = None,
        location_reference: str | None = None,
        limit: int = Query(default=10, ge=1, le=10),
    ) -> list[PolicySearchResultResponse]:
        result = await search_policy(
            session,
            PolicySearchInput(
                query=query,
                effective_on=effective_on or date.today(),
                policy_area=policy_area,
                location_reference=location_reference,
                limit=limit,
            ),
            HashingEmbeddingProvider(),
        )
        return [
            PolicySearchResultResponse.model_validate(hit.model_dump(mode="python"))
            for hit in result.data
        ]

    @app.post(
        "/api/operations/research",
        response_model=OperationsResearchResponse,
    )
    async def research_operations_records(
        payload: OperationsResearchRequest,
        _: OperationsAccountDependency,
        session: SessionDependency,
    ) -> OperationsResearchResponse:
        """Run the same bounded, read-only operational lookup available to the investigator."""

        request_type, function, evidence_type = TOOL_REGISTRY[payload.tool_name]
        try:
            request = request_type.model_validate(payload.arguments)
            result = await function(session, request)
        except (EntityNotFoundError, EntityOwnershipError) as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except (ToolError, ValidationError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        serialized = result.model_dump(mode="json")
        return OperationsResearchResponse(
            tool_name=payload.tool_name,
            evidence_type=evidence_type,
            metadata=serialized["metadata"],
            data=serialized["data"],
        )

    @app.get(
        "/api/operations/cases/{case_reference}",
        response_model=OperationsCaseWorkspaceResponse,
    )
    async def get_operations_case(
        case_reference: str,
        _: OperationsAccountDependency,
        session: SessionDependency,
    ) -> OperationsCaseWorkspaceResponse:
        workspace = await get_operations_case_workspace(session, case_reference=case_reference)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")

        actions: list[ActionDetailResponse] = []
        for intent, approval, decided_by in workspace.actions:
            attempts = [
                ExecutionAttemptResponse(
                    action_intent_reference=intent.public_reference,
                    attempt_number=item.attempt_number,
                    executor=item.executor,
                    status=item.status,
                    external_reference=item.external_reference,
                    response_payload=item.response_payload,
                    error_code=item.error_code,
                    error_detail=item.error_detail,
                    started_at=item.started_at,
                    completed_at=item.completed_at,
                )
                for item in workspace.execution_attempts
                if item.action_intent_id == intent.id
            ]
            actions.append(
                ActionDetailResponse(
                    public_reference=intent.public_reference,
                    action_type=intent.action_type,
                    target_type=intent.target_type,
                    target_reference=intent.target_reference,
                    action_payload=intent.action_payload,
                    status=intent.status,
                    created_at=intent.created_at,
                    approval=(
                        None
                        if approval is None
                        else ApprovalDetailResponse(
                            decision=approval.decision,
                            rationale=approval.rationale,
                            decided_at=approval.decided_at,
                            decided_by=decided_by,
                        )
                    ),
                    execution_attempts=attempts,
                )
            )

        run = workspace.run
        proposal = workspace.proposal
        verification = workspace.verification
        pending_action = next((item for item in actions if item.status == "pending_approval"), None)
        if pending_action is not None:
            recommendation_next_step = "Review and approve or reject the proposed action below."
        elif workspace.escalations:
            recommendation_next_step = "Review the evidence and continue the investigation."
        elif workspace.case.status == "resolved":
            recommendation_next_step = "No further action is required."
        else:
            recommendation_next_step = "Wait for case processing to finish."
        evidence_payload = [
            {
                "evidence_type": item.evidence_type,
                "condition": item.condition,
                "content": item.content,
            }
            for item in workspace.evidence
        ]
        return OperationsCaseWorkspaceResponse(
            **CaseResponse.model_validate(workspace.case).model_dump(),
            run=(
                None
                if run is None
                else CaseRunResponse(
                    run_number=run.run_number,
                    architecture_version=run.architecture_version,
                    model_provider=run.model_provider,
                    model_name=run.model_name,
                    status=run.status,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                    input_tokens=run.input_tokens,
                    output_tokens=run.output_tokens,
                    estimated_cost_usd=(
                        None if run.estimated_cost_usd is None else float(run.estimated_cost_usd)
                    ),
                    error_code=run.error_code,
                )
            ),
            plan=None if workspace.plan is None else workspace.plan.plan,
            stages=[
                WorkflowStageResponse(
                    stage_name=item.stage_name,
                    status=item.status,
                    attempt_count=item.attempt_count,
                    completed_at=item.completed_at,
                    error_code=item.error_code,
                )
                for item in workspace.stages
            ],
            evidence=[
                EvidenceResponse(
                    evidence_type=item.evidence_type,
                    condition=item.condition,
                    source_system=item.source_system,
                    source_reference=item.source_reference,
                    observed_as_of=item.observed_as_of,
                    content=item.content,
                )
                for item in workspace.evidence
            ],
            policy_retrievals=[
                PolicyRetrievalResponse(
                    query_text=item.query_text,
                    effective_on=item.effective_on,
                    selected_section_ids=item.selected_section_ids,
                    ranked_results=item.ranked_results,
                )
                for item in workspace.policy_retrievals
            ],
            proposal=(
                None
                if proposal is None
                else ProposalResponse(
                    outcome=proposal.outcome,
                    disposition=proposal.disposition,
                    rationale=proposal.rationale,
                    action_payload=proposal.action_payload,
                    evidence_references=proposal.evidence_references,
                    policy_references=proposal.policy_references,
                )
            ),
            verification=(
                None
                if verification is None
                else VerificationResponse(
                    supported=verification.supported,
                    missing_evidence=verification.missing_evidence,
                    contradictions=verification.contradictions,
                    unsupported_claims=verification.unsupported_claims,
                    recommended_outcome=verification.recommended_outcome,
                    recommended_disposition=verification.recommended_disposition,
                    requires_human=verification.requires_human,
                    rationale=verification.rationale,
                )
            ),
            recommendation=(
                None
                if proposal is None
                else RecommendationPresentationResponse.model_validate(
                    build_recommendation_presentation(
                        outcome=proposal.outcome,
                        supported=None if verification is None else verification.supported,
                        evidence=evidence_payload,
                        action_payload=proposal.action_payload,
                        proposal_rationale=proposal.rationale,
                        verification_rationale=(
                            None if verification is None else verification.rationale
                        ),
                        next_step=recommendation_next_step,
                    )
                )
            ),
            actions=actions,
            escalations=[
                EscalationResponse(
                    reason_code=item.reason_code,
                    details=item.details,
                    status=item.status,
                    created_at=item.created_at,
                    resolved_at=item.resolved_at,
                )
                for item in workspace.escalations
            ],
            final_communication=(
                None
                if workspace.final_communication is None
                else CustomerCommunicationResponse.model_validate(
                    workspace.final_communication[0]
                ).model_copy(update={"sent_by": workspace.final_communication[1]})
            ),
            events=[CaseEventResponse.model_validate(item) for item in workspace.events],
        )

    @app.put(
        "/api/operations/cases/{case_reference}/customer-communication/draft",
        response_model=CustomerCommunicationResponse,
    )
    async def update_customer_email_draft(
        case_reference: str,
        payload: CustomerEmailDraftRequest,
        account: OperationsAccountDependency,
        session: SessionDependency,
    ) -> CustomerCommunicationResponse:
        try:
            async with session.begin():
                communication = await update_final_email_draft(
                    session,
                    case_reference=case_reference,
                    account=account,
                    subject=payload.subject,
                    body=payload.body,
                )
                await session.refresh(communication)
                response = CustomerCommunicationResponse.model_validate(communication).model_copy(
                    update={"sent_by": None}
                )
        except CommunicationWorkflowError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return response

    @app.post(
        "/api/operations/cases/{case_reference}/customer-communication/send",
        response_model=CustomerCommunicationResponse,
    )
    async def mock_send_customer_email(
        case_reference: str,
        payload: CustomerEmailDraftRequest,
        account: OperationsAccountDependency,
        session: SessionDependency,
    ) -> CustomerCommunicationResponse:
        try:
            async with session.begin():
                communication = await mock_send_final_email(
                    session,
                    case_reference=case_reference,
                    account=account,
                    subject=payload.subject,
                    body=payload.body,
                )
                await session.refresh(communication)
                response = CustomerCommunicationResponse.model_validate(communication).model_copy(
                    update={"sent_by": account.display_name}
                )
        except CommunicationWorkflowError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return response

    @app.post(
        "/api/operations/cases/{case_reference}/investigation/acknowledge",
        response_model=InvestigationUpdateResponse,
    )
    async def acknowledge_operations_investigation(
        case_reference: str,
        account: OperationsAccountDependency,
        session: SessionDependency,
    ) -> InvestigationUpdateResponse:
        try:
            async with session.begin():
                result = await acknowledge_investigation(
                    session,
                    case_reference=case_reference,
                    account=account,
                )
        except InvestigationWorkflowError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return InvestigationUpdateResponse(
            case_status=result.case_status,
            escalation_status=result.escalation_status,
        )

    @app.post(
        "/api/operations/cases/{case_reference}/investigation/notes",
        response_model=InvestigationUpdateResponse,
    )
    async def add_operations_investigation_note(
        case_reference: str,
        payload: InvestigationNoteRequest,
        account: OperationsAccountDependency,
        session: SessionDependency,
    ) -> InvestigationUpdateResponse:
        try:
            async with session.begin():
                result = await add_investigation_note(
                    session,
                    case_reference=case_reference,
                    account=account,
                    note=payload.note,
                )
        except InvestigationWorkflowError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return InvestigationUpdateResponse(
            case_status=result.case_status,
            escalation_status=result.escalation_status,
        )

    @app.post(
        "/api/operations/cases/{case_reference}/investigation/resolve",
        response_model=InvestigationUpdateResponse,
    )
    async def resolve_operations_investigation(
        case_reference: str,
        payload: InvestigationResolutionRequest,
        account: OperationsAccountDependency,
        session: SessionDependency,
    ) -> InvestigationUpdateResponse:
        try:
            async with session.begin():
                result = await resolve_investigation(
                    session,
                    case_reference=case_reference,
                    account=account,
                    resolution_code=payload.resolution_code,
                    resolution_summary=payload.resolution_summary,
                    customer_response=payload.customer_response,
                )
        except InvestigationWorkflowError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return InvestigationUpdateResponse(
            case_status=result.case_status,
            escalation_status=result.escalation_status,
        )

    @app.get("/api/actions/pending", response_model=list[ActionIntentResponse])
    async def list_pending_actions(
        _: OperationsAccountDependency,
        session: SessionDependency,
        limit: int = 50,
    ) -> list[ActionIntentResponse]:
        rows = await session.execute(
            select(ActionIntent, SupportCase.public_reference)
            .join(SupportCase, SupportCase.id == ActionIntent.case_id)
            .where(
                ActionIntent.status == "pending_approval",
                ~SupportCase.external_request_key.startswith("eval:"),
            )
            .order_by(ActionIntent.created_at)
            .limit(max(1, min(limit, 200)))
        )
        return [
            ActionIntentResponse(
                public_reference=action.public_reference,
                case_reference=case_reference,
                action_type=action.action_type,
                target_type=action.target_type,
                target_reference=action.target_reference,
                action_payload=action.action_payload,
                status=action.status,
                created_at=action.created_at,
            )
            for action, case_reference in rows
        ]

    @app.post(
        "/api/actions/{action_reference}/decision",
        response_model=ApprovalResponse,
    )
    async def record_action_decision(
        action_reference: str,
        payload: ActionDecisionRequest,
        account: OperationsAccountDependency,
        session: SessionDependency,
    ) -> ApprovalResponse:
        try:
            async with session.begin():
                approval = await decide_action(
                    session,
                    action_reference=action_reference,
                    account=account,
                    decision=payload.decision,
                    rationale=payload.rationale,
                )
        except ActionValidationError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return ApprovalResponse.model_validate(approval)

    return app


app = create_app()
