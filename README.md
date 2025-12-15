# Local SEO Optimizer

자동화된 콘텐츠 생성 및 SEO 관리 SaaS for 로컬 비즈니스

## 🎯 Overview

Local SEO Optimizer는 소상공인을 위한 자동화된 SEO 솔루션입니다:

- **콘텐츠 자동 생성**: LLM(Gemini/OpenAI)을 활용한 플랫폼별 최적화 콘텐츠
- **AI 이미지 생성**: Google AI Studio Imagen 3를 활용한 자동 이미지 생성
- **승인 워크플로우**: AI 초안 → 카톡/슬랙 알림 → 사장님 승인 → 자동 업로드
- **멀티 플랫폼 업로드**: Google Business Profile, Instagram, Website(Blog)
- **성과 분석 & SEO 점수화**: 통합 대시보드 및 자동 추천
- **주간 리포트**: PDF 생성 및 이메일 발송
- **구독 결제**: Stripe 연동 플랜별 과금

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                        │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│   Auth      │  Content    │  Analytics  │   Billing       │
│   Router    │  Router     │  Router     │   Router        │
├─────────────┴─────────────┴─────────────┴─────────────────┤
│                      Services Layer                         │
│  ContentService │ PublisherService │ SEOService │ ...      │
├─────────────────────────────────────────────────────────────┤
│                    Integrations Layer                       │
│  LLM Adapter │ GBP Client │ IG Client │ Storage │ Email   │
├─────────────────────────────────────────────────────────────┤
│                      Data Layer                             │
│           PostgreSQL + SQLAlchemy + Alembic                │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Docker & Docker Compose (optional)

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/local-seo-optimizer.git
cd local-seo-optimizer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

### Using Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📚 API Documentation

After starting the server, access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/signup` | POST | User registration |
| `/auth/login` | POST | User authentication |
| `/auth/verify-email` | POST | Email verification |
| `/locations` | GET/POST | Manage business locations |
| `/locations/{id}/channels` | POST | Connect platforms (GBP/IG/Web) |
| `/oauth/google/authorize` | GET | Google OAuth flow |
| `/oauth/instagram/authorize` | GET | Instagram OAuth flow |
| `/content/generate` | POST | Generate content with LLM |
| `/approval/draft` | POST | Create draft with approval workflow |
| `/approval/posts/{id}/approve` | POST | Approve content |
| `/approval/posts/{id}/reject` | POST | Reject content |
| `/approval/pending` | GET | List pending approvals |
| `/posts` | GET/POST | Manage posts |
| `/posts/{id}/publish` | POST | Publish post to platform |
| `/analytics/summary` | GET | Get analytics summary |
| `/seo/score` | GET | Get SEO scores |
| `/billing/plans` | GET | List subscription plans |
| `/billing/checkout` | POST | Create checkout session |
| `/reports/weekly` | POST | Generate weekly report |

## 🔧 Configuration

### Environment Variables

```env
# Application
APP_ENV=dev|staging|prod
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db

# Authentication
JWT_SECRET=your-secret-key-min-32-chars

# LLM Provider
LLM_PROVIDER=gemini|openai
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key

# Platform APIs
GBP_CLIENT_ID=...
GBP_CLIENT_SECRET=...
IG_APP_ID=...
IG_APP_SECRET=...

# AWS (for storage)
AWS_REGION=us-east-1
S3_BUCKET=your-bucket

# Stripe (for billing)
STRIPE_SECRET_KEY=sk_...
```

## 📅 Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Content Generation | Mon 09:00 UTC | Generate weekly content |
| Publisher | Mon/Wed/Fri 10:00 UTC | Publish queued posts |
| Analytics Collection | Daily 01:00 UTC | Collect platform metrics |
| Weekly Report | Sun 18:00 UTC | Generate & send reports |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py -v
```

## 📁 Project Structure

```
local-seo-optimizer/
├── app/
│   ├── core/           # Config, security
│   ├── db/             # Database setup
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic schemas
│   ├── routers/        # API endpoints
│   ├── services/       # Business logic
│   ├── integrations/   # External APIs
│   ├── workers/        # Scheduled jobs
│   └── main.py         # FastAPI app
├── alembic/            # Database migrations
├── tests/              # Test suite
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## 🔐 Security

- JWT-based authentication with access/refresh tokens
- Password hashing with bcrypt
- Environment-based secrets management
- CORS configuration for production

## 🔄 Approval Workflow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  AI 콘텐츠    │───▶│  카톡/슬랙   │───▶│  사장님 승인  │───▶│  자동 업로드  │
│  초안 생성    │    │  알림 발송   │    │  버튼 클릭   │    │  (예약 가능)  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                                       │
       ▼                                       ▼
┌──────────────┐                        ┌──────────────┐
│  AI 이미지    │                        │  거절 시     │
│  자동 생성    │                        │  수정 요청   │
└──────────────┘                        └──────────────┘
```

### 알림 채널 지원
- **Slack**: Webhook을 통한 Block Kit 메시지 (승인/거절 버튼 포함)
- **KakaoTalk**: 알림톡 API 연동
- **Email**: SMTP를 통한 HTML 이메일

## 📈 Roadmap

- [x] OAuth integration (Google, Facebook)
- [x] Image generation with Imagen 3
- [x] Approval workflow with notifications
- [ ] Multi-language support
- [ ] Agency dashboard
- [ ] White-label options
- [ ] Mobile app

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

---

Built with ❤️ for local businesses
