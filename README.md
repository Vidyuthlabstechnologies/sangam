# Sangam — AI-Native Coordination Platform

Sangam is an AI-native coordination platform that enables organizations, AI agents, humans, services, and software to discover, communicate, negotiate, orchestrate workflows, exchange structured information, manage approvals, handle exceptions, and integrate through a unified developer platform.

## Architecture

```
sangam/
├── backend/          # Python FastAPI + Temporal (workflow engine)
├── android/          # Jetpack Compose (Material 3 Expressive)
├── web/              # React 19 + Refine + shadcn/ui
├── k8s/              # Kubernetes manifests (ArgoCD-ready)
├── sdk/
│   ├── python/       # Python SDK
│   └── typescript/   # TypeScript SDK
```

## Quick Start

### Prerequisites
- Python 3.12+
- Docker + Docker Compose
- Node.js 20+ (for web)
- Android Studio (for Android app)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### Docker (all services)

```bash
docker-compose up -d
```

This starts PostgreSQL, Redis, RabbitMQ, Temporal, and the Sangam backend.

### Web Dashboard

```bash
cd web
npm install
npm run dev
```

### Android App

Open `android/` in Android Studio and run on emulator or device.

## API

Once running, visit `http://localhost:8000/docs` for the interactive OpenAPI documentation.

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/workflows` | Create workflow |
| GET | `/workflows` | List workflows |
| GET | `/workflows/{id}` | Get workflow |
| PATCH | `/workflows/{id}` | Update workflow |
| POST | `/workflows/{id}/pause` | Pause workflow |
| POST | `/workflows/{id}/resume` | Resume workflow |
| POST | `/workflows/{id}/cancel` | Cancel workflow |
| POST | `/actors` | Create actor |
| GET | `/actors` | List actors |
| POST | `/approvals/{id}/approve` | Approve |
| POST | `/approvals/{id}/reject` | Reject |

## Core Concepts

- **Workflows**: First-class citizens with initiation, approval, execution, verification, settlement, and exception phases
- **Actors**: Humans, AI agents, and systems that participate equally
- **Approvals**: Multi-party with any/all/threshold strategies, conditional rules, escalation
- **Handoffs**: Traceable transfers between actors with artifact verification
- **Exceptions**: Bounded sub-workflows with their own lifecycles
- **Waiting Events**: Observable, SLA-bound pauses in workflow execution

## Deployment

```bash
kubectl create namespace sangam
kubectl apply -f k8s/ -n sangam
```

## License

MIT
