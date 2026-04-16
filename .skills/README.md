# LLM Skills Library

Skills descargadas, curadas y creadas para el proyecto Cosmetica 5 ERP.

Fuentes originales:
- [awesome-llm-skills](https://github.com/Prat011/awesome-llm-skills) (1.1k stars)
- [claude-skills](https://github.com/Jeffallan/claude-skills) (66 skills, 659 forks)
- Skills propias del proyecto (marcadas como "Custom")

## Skills Disponibles

### Core del Proyecto (Custom — Django ERP Stack)

| Skill | Dominio | Uso |
|-------|---------|-----|
| `django-expert` | Backend | Django 4.x, ORM, managers, middleware, signals, admin, settings — **CUSTOM** |
| `drf-specialist` | Backend | DRF ViewSets, serializers, permissions, throttling, pagination, OpenAPI — **CUSTOM** |
| `postgresql-pro` | Database | PostgreSQL 15, indexes, EXPLAIN, constraints, multi-tenant queries — **CUSTOM** |
| `nextjs-frontend` | Frontend | Next.js 14, App Router, React Query, next-intl, Zod, TailwindCSS — **CUSTOM** |
| `migration-safety` | Database | Zero-downtime migrations, data migrations, squashing, rollback — **CUSTOM** |
| `celery-worker` | Backend | Celery tasks, retries, periodic jobs, Redis broker, monitoring — **CUSTOM** |

### Lenguaje & Calidad

| Skill | Dominio | Uso |
|-------|---------|-----|
| `python-pro` | Language | Python 3.11+, type hints, async, pytest, mypy |
| `test-master` | Quality | Unit/integration/E2E tests, coverage, test plans |
| `code-reviewer` | Quality | PR reviews, code quality audits, security checks |
| `debugging-wizard` | Quality | Error diagnosis, stack traces, systematic debugging |
| `secure-code-guardian` | Security | OWASP Top 10, auth, encryption, input validation |

### Arquitectura & DevOps

| Skill | Dominio | Uso |
|-------|---------|-----|
| `api-designer` | Architecture | REST/GraphQL, OpenAPI 3.1, RFC 7807 |
| `architecture-designer` | Architecture | System design, ADRs, patterns, scalability |
| `devops-engineer` | DevOps | CI/CD, Docker, K8s, Terraform, GitHub Actions |
| `feature-forge` | Workflow | Requirements, EARS specs, acceptance criteria |

### Utilidades (bajo uso en este proyecto)

| Skill | Dominio | Uso |
|-------|---------|-----|
| `prompt-engineer` | Data/ML | Prompt optimization, CoT, few-shot |
| `mcp-builder` | MCP | Building MCP servers |
| `mcp-developer` | MCP | MCP server/client implementation |
| `pandas-pro` | Data/ML | DataFrame operations, data cleaning |
| `skill-creator` | Meta | Creating new skills, SKILL.md format |
| `swiftui-animator` | Mobile/UI | SwiftUI motion design |
| `playful-mobile-ui` | Mobile/UI | GenZ/social app design |

## Cómo Usar

Estas skills se cargan automáticamente cuando el prompt del usuario coincide con los `triggers` del YAML frontmatter.
Cada `SKILL.md` contiene: workflow, constraints, code examples, y notas específicas del proyecto.

## Notas del Proyecto

- **Python runtime**: 3.9 (no 3.11) — usar `Optional[str]` en vez de `str | None`
- **Django 4.2.8** + DRF 3.14.0 + PostgreSQL 15
- **Multi-tenant**: LegalEntity como modelo de tenant
- **RULE.md**: Directrices obligatorias para Claude (evidence packs, no improvements no pedidos)

Fecha de última actualización: 2026-04-16
