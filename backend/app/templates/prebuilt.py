from app.templates.registry import WorkflowTemplate, PhaseTemplate, ApprovalStepTemplate
from app.models.workflow import WorkflowPhase
from app.models.actor import Role


def get_all_templates() -> list[WorkflowTemplate]:
    return [
        procurement_template(),
        expense_approval_template(),
        employee_onboarding_template(),
        vendor_kyc_template(),
        contract_review_template(),
        incident_response_template(),
        leave_approval_template(),
        purchase_request_template(),
        invoice_processing_template(),
        compliance_audit_template(),
        change_request_template(),
        recruitment_pipeline_template(),
    ]


def procurement_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="procurement-standard",
        name="Standard Procurement",
        description="End-to-end procurement workflow from requisition to settlement",
        category="procurement",
        tags=["procurement", "purchase", "enterprise"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Requisition",
                description="Submit purchase requisition with specifications", estimated_minutes=30),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Budget Approval",
                description="Budget owner reviews and approves requisition", estimated_minutes=240),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="PO Generation",
                description="Generate purchase order and send to vendor", estimated_minutes=60),
            PhaseTemplate(phase=WorkflowPhase.VERIFICATION, label="Goods Receipt",
                description="Verify received goods against PO", estimated_minutes=120),
            PhaseTemplate(phase=WorkflowPhase.SETTLEMENT, label="Payment",
                description="Process vendor payment", estimated_minutes=1440),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Budget Approval", required_roles=[Role.MANAGER],
                strategy="all", sla_minutes=1440),
            ApprovalStepTemplate(label="Finance Approval", required_roles=[Role.APPROVER],
                strategy="any", condition="{{amount}} > 50000"),
        ],
    )


def expense_approval_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="expense-approval",
        name="Expense Approval",
        description="Employee expense claim review and reimbursement",
        category="finance",
        tags=["expense", "reimbursement", "finance"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Claim Submission",
                description="Submit expense report with receipts", estimated_minutes=20),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Manager Review",
                description="Manager verifies and approves expenses", estimated_minutes=120),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Validation",
                description="Finance team validates receipts and policy compliance", estimated_minutes=60),
            PhaseTemplate(phase=WorkflowPhase.SETTLEMENT, label="Reimbursement",
                description="Process payment to employee", estimated_minutes=2880),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Manager Approval", required_roles=[Role.MANAGER],
                strategy="all", sla_minutes=1440),
        ],
    )


def employee_onboarding_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="employee-onboarding",
        name="Employee Onboarding",
        description="New employee onboarding across HR, IT, and facilities",
        category="hr",
        tags=["onboarding", "hr", "it"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Offer Acceptance",
                description="Candidate accepts offer letter", estimated_minutes=60),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Background Check",
                description="Verify credentials and run background check", estimated_minutes=4320),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="IT Setup",
                description="Provision laptop, email, and access", estimated_minutes=1440),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Facilities",
                description="Assign desk, badge, and parking", estimated_minutes=1440),
            PhaseTemplate(phase=WorkflowPhase.VERIFICATION, label="Day 1 Readiness",
                description="Verify all setups are complete before start date", estimated_minutes=60),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Hire Approval", required_roles=[Role.MANAGER, Role.ADMIN],
                strategy="all"),
        ],
    )


def vendor_kyc_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="vendor-kyc",
        name="Vendor KYC",
        description="Vendor registration and KYC verification",
        category="procurement",
        tags=["vendor", "kyc", "compliance"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Registration",
                description="Vendor submits registration form and documents", estimated_minutes=30),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Document Verification",
                description="Verify GST, PAN, bank details", estimated_minutes=1440),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Background Check",
                description="Run compliance and sanction screening", estimated_minutes=2880),
            PhaseTemplate(phase=WorkflowPhase.VERIFICATION, label="Final Review",
                description="Review committee approves vendor onboarding", estimated_minutes=120),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Compliance Check", required_roles=[Role.APPROVER],
                strategy="all", sla_minutes=4320),
        ],
    )


def contract_review_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="contract-review",
        name="Contract Review",
        description="Legal review and approval of contracts and agreements",
        category="legal",
        tags=["contract", "legal", "review"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Draft Submission",
                description="Submit contract draft for review", estimated_minutes=60),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Legal Review",
                description="Legal team reviews terms and conditions", estimated_minutes=2880),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Negotiation",
                description="Negotiate changes with counter-party", estimated_minutes=4320),
            PhaseTemplate(phase=WorkflowPhase.VERIFICATION, label="Final Approval",
                description="Authorized signatory approves final version", estimated_minutes=120),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Legal Review", required_roles=[Role.APPROVER],
                strategy="all", sla_minutes=4320),
            ApprovalStepTemplate(label="Executive Sign-off", required_roles=[Role.ADMIN],
                strategy="any", condition="{{amount}} > 100000"),
        ],
    )


def incident_response_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="incident-response",
        name="Incident Response",
        description="Security incident detection, triage, and resolution",
        category="security",
        tags=["incident", "security", "sre"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Detection",
                description="Alert triggered by monitoring system", estimated_minutes=5),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Triage",
                description="Assess severity and assign responders", estimated_minutes=15),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Containment",
                description="Isolate affected systems", estimated_minutes=30),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Eradication",
                description="Remove root cause", estimated_minutes=120),
            PhaseTemplate(phase=WorkflowPhase.VERIFICATION, label="Recovery",
                description="Restore services and verify", estimated_minutes=60),
            PhaseTemplate(phase=WorkflowPhase.SETTLEMENT, label="Postmortem",
                description="Document lessons learned", estimated_minutes=120),
        ],
        default_actor_types=["agent", "human"],
    )


def leave_approval_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="leave-approval",
        name="Leave Approval",
        description="Employee leave request and approval workflow",
        category="hr",
        tags=["leave", "hr", "attendance"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Request",
                description="Employee submits leave request", estimated_minutes=5),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Manager Approval",
                description="Manager reviews and approves leave", estimated_minutes=120),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="HR Verification",
                description="HR checks leave balance and policy", estimated_minutes=60),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Manager Approval", required_roles=[Role.MANAGER],
                strategy="all", sla_minutes=1440),
        ],
    )


def purchase_request_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="purchase-request",
        name="Purchase Request",
        description="Simple purchase request for low-value items",
        category="procurement",
        tags=["purchase", "request"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Request",
                description="Request item with justification", estimated_minutes=10),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Approval",
                description="Department head approves request", estimated_minutes=120),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Fulfillment",
                description="Procurement team procures item", estimated_minutes=2880),
            PhaseTemplate(phase=WorkflowPhase.VERIFICATION, label="Delivery",
                description="Verify item received and in good condition", estimated_minutes=60),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Department Approval", required_roles=[Role.MANAGER],
                strategy="all", sla_minutes=1440),
            ApprovalStepTemplate(label="Finance Approval", required_roles=[Role.APPROVER],
                strategy="any", condition="{{amount}} > 10000"),
        ],
    )


def invoice_processing_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="invoice-processing",
        name="Invoice Processing",
        description="Vendor invoice receipt, validation, and payment",
        category="finance",
        tags=["invoice", "accounts-payable", "finance"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Invoice Receipt",
                description="Receive invoice from vendor", estimated_minutes=10),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Data Extraction",
                description="Extract invoice data via OCR", estimated_minutes=5),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Validation",
                description="Match invoice against PO and goods receipt", estimated_minutes=120),
            PhaseTemplate(phase=WorkflowPhase.VERIFICATION, label="Audit Check",
                description="Verify tax compliance and accounting codes", estimated_minutes=60),
            PhaseTemplate(phase=WorkflowPhase.SETTLEMENT, label="Payment",
                description="Schedule and process payment", estimated_minutes=1440),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Invoice Match", required_roles=[Role.APPROVER],
                strategy="all", sla_minutes=2880),
        ],
        default_actor_types=["agent", "human"],
    )


def compliance_audit_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="compliance-audit",
        name="Compliance Audit",
        description="Internal compliance audit with evidence collection",
        category="compliance",
        tags=["compliance", "audit", "regulatory"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Audit Planning",
                description="Define scope and objectives", estimated_minutes=120),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Evidence Collection",
                description="Gather and review compliance evidence", estimated_minutes=4320),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Finding Review",
                description="Review audit findings with process owners", estimated_minutes=240),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Remediation",
                description="Address identified gaps", estimated_minutes=10080),
            PhaseTemplate(phase=WorkflowPhase.VERIFICATION, label="Close-out",
                description="Verify remediation and close audit", estimated_minutes=120),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Audit Approval", required_roles=[Role.ADMIN],
                strategy="all", sla_minutes=1440),
        ],
    )


def change_request_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="change-request",
        name="Change Request",
        description="IT change request with CAB approval",
        category="it",
        tags=["change", "itil", "cab"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Request",
                description="Submit change request with impact assessment", estimated_minutes=30),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="CAB Review",
                description="Change Advisory Board reviews and approves", estimated_minutes=1440),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Implementation",
                description="Execute the change", estimated_minutes=120),
            PhaseTemplate(phase=WorkflowPhase.VERIFICATION, label="Post-Implementation",
                description="Verify change success and rollback if needed", estimated_minutes=60),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Manager Review", required_roles=[Role.MANAGER],
                strategy="all", sla_minutes=1440),
            ApprovalStepTemplate(label="CAB Approval", required_roles=[Role.APPROVER, Role.ADMIN],
                strategy="all", condition="{{risk_level}} == 'high'"),
        ],
    )


def recruitment_pipeline_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="recruitment-pipeline",
        name="Recruitment Pipeline",
        description="End-to-end candidate recruitment and hiring",
        category="hr",
        tags=["recruitment", "hiring", "hr"],
        phases=[
            PhaseTemplate(phase=WorkflowPhase.INITIATION, label="Requisition",
                description="Hiring manager submits headcount request", estimated_minutes=30),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Requisition Approval",
                description="HR and budget approval for the role", estimated_minutes=1440),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Sourcing",
                description="Source candidates and screen applications", estimated_minutes=4320),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Interviews",
                description="Technical and HR interviews", estimated_minutes=4320),
            PhaseTemplate(phase=WorkflowPhase.APPROVAL, label="Selection",
                description="Hiring committee selects candidate", estimated_minutes=120),
            PhaseTemplate(phase=WorkflowPhase.EXECUTION, label="Offer",
                description="Extend offer and negotiate", estimated_minutes=1440),
        ],
        approval_steps=[
            ApprovalStepTemplate(label="Budget Approval", required_roles=[Role.MANAGER, Role.ADMIN],
                strategy="all", sla_minutes=4320),
            ApprovalStepTemplate(label="Selection Approval", required_roles=[Role.MANAGER, Role.APPROVER],
                strategy="all"),
        ],
    )
