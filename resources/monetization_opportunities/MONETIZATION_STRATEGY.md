# Monetization Strategy & Business Readiness

## Executive Summary

This document outlines monetization opportunities for the Statement Data Extraction platform, a medical invoice/financial document parsing system with a 3-phase inference pipeline (keyword matching → LLM fallback → human review). The platform is currently deployed on Azure with FastAPI.

---

## 1. Monetization Opportunities

### 1.1 Web Application / SaaS (Recommended)

#### A. Healthcare Claims Automation SaaS
| Aspect | Details |
|--------|---------|
| **Target Market** | Insurance companies, Third Party Administrators (TPAs), clinic groups in Singapore |
| **Revenue Model** | Per-document pricing ($0.10-0.50/doc) or monthly subscription ($200-500/month) |
| **Value Proposition** | Automated invoice parsing with human-in-the-loop for compliance |
| **Feasibility** | **High** - Strong fit given Singapore healthcare focus |

#### B. Accounting/Bookkeeping Tool
| Aspect | Details |
|--------|---------|
| **Target Market** | SMEs, freelancers, accounting firms |
| **Revenue Model** | Freemium (X docs/month free, then paid tiers) |
| **Value Proposition** | Bank statement + medical expense tracking for tax/audit |
| **Feasibility** | **Medium** - Competitive market, but bank parsing adds differentiation |

#### C. API-as-a-Service
| Aspect | Details |
|--------|---------|
| **Target Market** | Developers building fintech/insurtech applications |
| **Revenue Model** | Usage-based pricing (per API call) |
| **Value Proposition** | Drop-in document intelligence for existing apps |
| **Feasibility** | **High** - Already has FastAPI with `/parse` endpoints |

### 1.2 Mobile App (Lower Priority)

| Opportunity | Target | Model | Challenges |
|-------------|--------|-------|------------|
| Personal Medical Expense Tracker | Individuals | One-time ($5-15) or subscription | Small market, high competition |
| Receipt Scanner for Insurance Claims | Policyholders | B2B (insurance company pays) | Requires partnership first |

**Why mobile is weaker:**
- PDF processing is compute-heavy (not ideal for mobile)
- Consumer market expects free apps
- 3-phase inference pipeline is overkill for casual users
- Better as a backend service that a mobile app calls via API

### 1.3 Recommended Go-to-Market Strategy

```
Phase 1: B2B SaaS for Singapore Healthcare
    └── Target: Insurance TPAs, clinic chains, corporate HR
    └── Pricing: Per-document or monthly subscription
    └── Differentiation: HITL flagging for compliance

Phase 2: Developer API Marketplace
    └── List on RapidAPI, AWS Marketplace
    └── Free tier (100 docs/month) → Paid tiers
    └── Target: Insurtech/fintech startups

Phase 3: Expand to Adjacent Markets
    └── Other ASEAN countries (Malaysia, Thailand)
    └── Additional document types (receipts, contracts)
```

---

## 2. Competitive Advantages

| Strength | Business Value |
|----------|----------------|
| Singapore healthcare context | Niche but defensible market position |
| Maker-checker (HITL) design | Appeals to regulated industries |
| Confidence scoring | Enables SLA-based pricing ("99% accuracy guarantee") |
| 3-phase inference | Cost-efficient (keywords first, LLM only when needed) |
| Already has REST API | Low effort to productize |
| Azure deployment ready | Enterprise credibility |

---

## 3. Business Readiness Checklist

### 3.1 Technical Infrastructure

#### A. API & Backend
- [ ] **Rate limiting** - Prevent abuse and enable tiered pricing
- [ ] **API key management** - Issue/revoke keys per customer
- [ ] **Usage metering** - Track API calls per customer for billing
- [ ] **Webhook support** - Notify customers when async processing completes
- [ ] **API versioning** - `/v1/parse`, `/v2/parse` for backwards compatibility
- [ ] **OpenAPI documentation** - Auto-generated Swagger/ReDoc (FastAPI has this)

#### B. Scalability
- [ ] **Azure auto-scaling** - Scale App Service based on CPU/memory/requests
- [ ] **Background job processing** - Celery + Redis for async document processing
- [ ] **Queue-based architecture** - Handle burst traffic gracefully
- [ ] **CDN for static assets** - Azure CDN or Cloudflare
- [ ] **Database selection** - PostgreSQL for transactional data, blob storage for PDFs

#### C. Reliability
- [ ] **Health checks** - Already have `/health` endpoint
- [ ] **Monitoring & alerting** - Azure Monitor, Application Insights
- [ ] **Logging** - Structured logging with correlation IDs
- [ ] **Error tracking** - Sentry or similar for production errors
- [ ] **Backup & recovery** - Automated database backups

### 3.2 Security & Compliance

- [ ] **Authentication** - OAuth2 / JWT for API access
- [ ] **Data encryption** - At rest (Azure Storage) and in transit (TLS)
- [ ] **PDPA compliance** - Singapore Personal Data Protection Act
- [ ] **Data retention policies** - Auto-delete processed documents after X days
- [ ] **Audit logging** - Track who accessed what data when
- [ ] **Penetration testing** - Before public launch
- [ ] **SOC 2 Type II** - For enterprise customers (long-term goal)

### 3.3 Business Operations

#### A. Billing & Payments
- [ ] **Payment gateway** - Stripe for subscriptions and usage-based billing
- [ ] **Invoice generation** - Automated monthly invoices
- [ ] **Usage dashboards** - Customer-facing portal showing API usage
- [ ] **Trial periods** - 14-day free trial with credit card

#### B. Customer Support
- [ ] **Documentation site** - GitBook, Docusaurus, or ReadTheDocs
- [ ] **API playground** - Interactive testing (already have GUI at `/`)
- [ ] **Support ticketing** - Zendesk, Freshdesk, or Intercom
- [ ] **SLA definitions** - Response times, uptime guarantees

#### C. Legal
- [ ] **Terms of Service** - API usage terms
- [ ] **Privacy Policy** - Data handling practices
- [ ] **Data Processing Agreement** - For enterprise customers
- [ ] **Business registration** - Singapore company if targeting local market

---

## 4. Learning Roadmap

### 4.1 FastAPI Deep Dive
| Topic | Why It Matters | Resources |
|-------|----------------|-----------|
| Dependency injection | Clean authentication, database sessions | [FastAPI Docs - Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) |
| Background tasks | Async document processing | [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) |
| Middleware | Rate limiting, logging, CORS | [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/) |
| Security (OAuth2, JWT) | API authentication | [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) |
| Testing with httpx | Async test client | [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/) |
| WebSockets | Real-time processing status | [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) |

### 4.2 Azure Production Deployment
| Topic | Why It Matters | Resources |
|-------|----------------|-----------|
| App Service auto-scaling | Handle variable load | [Azure Autoscale](https://learn.microsoft.com/en-us/azure/app-service/manage-scale-up) |
| Azure Functions | Serverless for lightweight endpoints | [Azure Functions Python](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python) |
| Azure Container Apps | Kubernetes-lite for containers | [Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/) |
| Application Insights | Monitoring, APM, logging | [App Insights](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview) |
| Azure Key Vault | Secrets management | [Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/) |
| Azure Blob Storage | PDF storage with lifecycle policies | [Blob Storage](https://learn.microsoft.com/en-us/azure/storage/blobs/) |
| Azure Front Door | CDN + WAF + load balancing | [Front Door](https://learn.microsoft.com/en-us/azure/frontdoor/) |

### 4.3 Background Processing
| Topic | Why It Matters | Resources |
|-------|----------------|-----------|
| Celery + Redis | Async task queues | [Celery Docs](https://docs.celeryq.dev/) |
| Azure Service Bus | Enterprise message queue | [Service Bus](https://learn.microsoft.com/en-us/azure/service-bus-messaging/) |
| Azure Queue Storage | Lightweight queue alternative | [Queue Storage](https://learn.microsoft.com/en-us/azure/storage/queues/) |

### 4.4 Database & Storage
| Topic | Why It Matters | Resources |
|-------|----------------|-----------|
| SQLAlchemy + Alembic | ORM + migrations | [SQLAlchemy Docs](https://docs.sqlalchemy.org/) |
| Azure PostgreSQL | Managed database | [Azure PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/) |
| Redis caching | API response caching | [Redis Docs](https://redis.io/docs/) |

### 4.5 Business & Product
| Topic | Why It Matters | Resources |
|-------|----------------|-----------|
| Stripe Billing | Subscriptions, usage-based billing | [Stripe Billing](https://stripe.com/docs/billing) |
| PostHog / Mixpanel | Product analytics | [PostHog Docs](https://posthog.com/docs) |
| Customer interviews | Validate pricing, features | [The Mom Test](https://www.momtestbook.com/) |
| Singapore insurtech landscape | Competitor analysis | Research: Great Eastern, NTUC Income, Prudential APIs |

---

## 5. Pricing Strategy

### 5.1 B2B SaaS Tiers

| Tier | Price | Included | Target |
|------|-------|----------|--------|
| **Starter** | $99/month | 500 documents, email support | Small clinics |
| **Professional** | $299/month | 2,000 documents, API access, priority support | Medium TPAs |
| **Enterprise** | Custom | Unlimited, SLA, dedicated support, on-prem option | Insurance companies |

### 5.2 API Pricing (Developer Tier)

| Tier | Price | Requests/month | Features |
|------|-------|----------------|----------|
| **Free** | $0 | 100 | Rate limited, watermarked |
| **Developer** | $49/month | 1,000 | Full API access |
| **Startup** | $199/month | 10,000 | Webhooks, priority |
| **Scale** | $0.05/request | Unlimited | Volume discounts |

### 5.3 Cost Structure Considerations

| Cost Component | Estimated | Notes |
|----------------|-----------|-------|
| Azure App Service (B1) | ~$55/month | Basic tier |
| Azure App Service (P1V2) | ~$150/month | Production tier with auto-scale |
| OpenAI API (GPT-4o-mini) | ~$0.001/doc | Only for inference fallback |
| Azure Blob Storage | ~$0.02/GB | PDF storage |
| Stripe fees | 2.9% + $0.30 | Per transaction |

**Break-even analysis:** At $99/month with ~$200/month infrastructure costs, need ~3 paying customers to break even.

---

## 6. MVP Feature Priorities

### Must Have (Launch)
- [x] Core parsing functionality
- [x] REST API endpoints
- [x] Health checks
- [ ] API key authentication
- [ ] Basic rate limiting
- [ ] Usage tracking
- [ ] Landing page with pricing

### Should Have (Month 2-3)
- [ ] Customer dashboard (usage, billing)
- [ ] Stripe integration
- [ ] Email notifications
- [ ] Multiple API keys per customer
- [ ] Webhook notifications

### Nice to Have (Month 4+)
- [ ] Multi-bank support (OCBC, UOB)
- [ ] Batch processing endpoint
- [ ] White-label option
- [ ] Mobile-responsive web app
- [ ] Slack/Teams integration

---

## 7. Next Steps

1. **Validate demand** - Talk to 5-10 potential customers (clinic admins, TPA managers)
2. **Add authentication** - Implement API key management
3. **Set up Stripe** - Basic subscription billing
4. **Create landing page** - Simple marketing site with pricing
5. **Soft launch** - Invite 3-5 beta customers
6. **Iterate based on feedback** - Refine pricing and features

---

## Appendix: Useful Commands

```bash
# Run locally with auto-reload
uvicorn src.api.medical_invoice_api:app --reload --port 8000

# Run tests
pytest tests/ -v

# Check code quality
ruff check src/
ruff format src/

# Build Docker image
docker build -f Dockerfile.azure -t statement-parser .

# Deploy to Azure (assuming az cli configured)
az webapp up --name statement-parser --resource-group myResourceGroup
```

---

*Last updated: January 2026*
