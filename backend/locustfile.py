from locust import HttpUser, task, between, tag
import random
import json

USER_EMAILS = [f"test{i}@sangam.ai" for i in range(1, 51)]
WORKFLOW_NAMES = [
    "Procurement Request", "Vendor KYC", "Expense Report",
    "Employee Onboarding", "Contract Review", "Change Request",
    "Incident Response", "Compliance Audit", "Invoice Processing",
    "Recruitment Pipeline",
]


class SangamUser(HttpUser):
    wait_time = between(1, 3)
    token = None
    actor_id = None

    def on_start(self):
        email = random.choice(USER_EMAILS)
        name = email.split("@")[0]
        try:
            resp = self.client.post(
                "/auth/register",
                json={"name": name, "email": email, "password": "test123"},
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data["access_token"]
                self.actor_id = data["actor_id"]
        except Exception:
            try:
                resp = self.client.post(
                    "/auth/login",
                    json={"email": email, "password": "test123"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data["access_token"]
                    self.actor_id = data["actor_id"]
            except Exception:
                pass

    @tag("workflows")
    @task(5)
    def list_workflows(self):
        if not self.token:
            return
        self.client.get(
            "/workflows",
            headers={"Authorization": f"Bearer {self.token}"},
            name="list_workflows",
        )

    @tag("workflows")
    @task(3)
    def create_workflow(self):
        if not self.token:
            return
        name = random.choice(WORKFLOW_NAMES)
        phases = random.sample(
            ["INITIATION", "APPROVAL", "EXECUTION", "VERIFICATION", "SETTLEMENT"],
            k=random.randint(2, 4),
        )
        self.client.post(
            "/workflows",
            json={"name": f"{name} - {random.randint(1000,9999)}", "phases": phases},
            headers={"Authorization": f"Bearer {self.token}"},
            name="create_workflow",
        )

    @tag("actors")
    @task(2)
    def list_actors(self):
        if not self.token:
            return
        self.client.get(
            "/actors",
            headers={"Authorization": f"Bearer {self.token}"},
            name="list_actors",
        )

    @tag("analytics")
    @task(2)
    def get_analytics(self):
        self.client.get("/analytics/summary", name="analytics_summary")

    @tag("ai")
    @task(1)
    def ai_llm(self):
        if not self.token:
            return
        self.client.post(
            "/ai/llm",
            json={
                "messages": [{"role": "user", "content": "Say hello in 5 words"}],
                "max_tokens": 50,
            },
            headers={"Authorization": f"Bearer {self.token}"},
            name="ai_llm",
            timeout=60,
        )

    @tag("ai")
    @task(1)
    def ai_translate(self):
        if not self.token:
            return
        self.client.post(
            "/ai/translate",
            json={"text": "Hello world", "target_language_code": "hi-IN"},
            headers={"Authorization": f"Bearer {self.token}"},
            name="ai_translate",
            timeout=30,
        )

    @tag("ai")
    @task(1)
    def ai_languages(self):
        if not self.token:
            return
        self.client.get(
            "/ai/languages",
            headers={"Authorization": f"Bearer {self.token}"},
            name="ai_languages",
        )

    @tag("approvals")
    @task(2)
    def list_approvals(self):
        if not self.token:
            return
        self.client.get(
            f"/workflows",
            headers={"Authorization": f"Bearer {self.token}"},
            name="approvals_context",
        )

    @tag("health")
    @task(1)
    def health_check(self):
        self.client.get("/health", name="health")


class AIHeavyUser(HttpUser):
    wait_time = between(3, 8)
    token = None

    def on_start(self):
        email = f"ai_user_{random.randint(1,9999)}@sangam.ai"
        try:
            resp = self.client.post(
                "/auth/register",
                json={"name": "AI Heavy User", "email": email, "password": "test123"},
            )
            if resp.status_code == 200:
                self.token = resp.json()["access_token"]
        except Exception:
            pass

    @tag("ai-heavy")
    @task(1)
    def llm_long(self):
        if not self.token:
            return
        self.client.post(
            "/ai/llm",
            json={
                "messages": [
                    {"role": "user", "content": "Write a detailed analysis of workflow automation trends in enterprise systems, covering at least 200 words."}
                ],
                "max_tokens": 500,
                "temperature": 0.3,
            },
            headers={"Authorization": f"Bearer {self.token}"},
            name="ai_llm_long",
            timeout=120,
        )

    @tag("ai-heavy")
    @task(1)
    def text_analytics(self):
        if not self.token:
            return
        self.client.post(
            "/ai/text-analytics",
            json={
                "text": "The workflow was initiated by the finance team. After approval from the manager, it was forwarded to the vendor for execution. The vendor completed the work within the SLA timeframe.",
                "questions": [
                    {"question": "Who initiated the workflow?", "context": "Looking for the team name"},
                    {"question": "What was the outcome?", "context": "Was the work completed?"},
                ],
            },
            headers={"Authorization": f"Bearer {self.token}"},
            name="ai_text_analytics",
            timeout=60,
        )

    @tag("ai-heavy")
    @task(1)
    def identify_language(self):
        if not self.token:
            return
        self.client.post(
            "/ai/identify-language",
            json={"text": "नमस्ते, आप कैसे हैं? मुझे एक वर्कफ़्लो बनाना है"},
            headers={"Authorization": f"Bearer {self.token}"},
            name="ai_identify_language",
            timeout=15,
        )
