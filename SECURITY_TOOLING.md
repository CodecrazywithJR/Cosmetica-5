# Security Tooling Stack

This document describes the automated security and static analysis tools integrated into the ERP backend.

> **Important:** These tools run in development and CI only.
> They do NOT modify runtime behavior or production dependencies.

---

## Quick Reference

| Tool | Purpose | Command |
|------|---------|---------|
| **Bandit** | Python SAST scanner | `bandit -r apps/api -c .bandit` |
| **pip-audit** | Dependency vulnerability scan | `pip-audit -r apps/api/requirements.txt` |
| **detect-secrets** | Prevent committing credentials | `detect-secrets scan` |
| **Semgrep** | Advanced static security analysis | `semgrep scan` |
| **Trivy** | Container & filesystem vuln scan | `trivy fs .` |
| **SonarQube** | Code quality & security analysis | `sonar-scanner` |
| **Snyk** | Dependency security monitoring | `snyk test` |

---

## 1. Bandit — Python SAST Scanner

**What it does:** Scans Python source code for common security issues (SQL injection, hardcoded passwords, unsafe deserialization, etc.).

**Configuration:** [.bandit](.bandit)

**Local usage:**

```bash
# Basic scan
bandit -r apps/api -c .bandit

# JSON output (for CI)
bandit -r apps/api -c .bandit -f json -o bandit-report.json

# Scan with high severity only
bandit -r apps/api -c .bandit -ll
```

**CI usage:**

```yaml
- name: Bandit Security Scan
  run: |
    pip install bandit
    bandit -r apps/api -c .bandit -f json -o bandit-report.json
```

---

## 2. pip-audit — Dependency Vulnerability Scanner

**What it does:** Checks installed Python packages against the Python Packaging Advisory Database (PyPI) and OSV for known vulnerabilities.

**Local usage:**

```bash
# Scan from requirements file
pip-audit -r apps/api/requirements.txt

# Scan installed packages
pip-audit

# JSON output (for CI)
pip-audit -r apps/api/requirements.txt -f json -o pip-audit-report.json

# Auto-fix (upgrade vulnerable packages)
pip-audit -r apps/api/requirements.txt --fix
```

**CI usage:**

```yaml
- name: pip-audit Dependency Scan
  run: |
    pip install pip-audit
    pip-audit -r apps/api/requirements.txt
```

---

## 3. detect-secrets — Credential Leak Prevention

**What it does:** Scans the codebase for accidentally committed secrets (API keys, passwords, tokens) and maintains a baseline of known/allowed entries.

**Configuration:** [.secrets.baseline](.secrets.baseline)

**Local usage:**

```bash
# Regenerate baseline (run once, then commit the file)
detect-secrets scan > .secrets.baseline

# Audit current baseline (interactive)
detect-secrets audit .secrets.baseline

# Check for new secrets (CI mode — exits non-zero if new secrets found)
detect-secrets scan --baseline .secrets.baseline
```

**Pre-commit hook setup:**

```bash
# Install as pre-commit hook
pip install pre-commit
# Add to .pre-commit-config.yaml:
#   - repo: https://github.com/Yelp/detect-secrets
#     rev: v1.5.0
#     hooks:
#       - id: detect-secrets
#         args: ['--baseline', '.secrets.baseline']
```

**CI usage:**

```yaml
- name: detect-secrets Check
  run: |
    pip install detect-secrets
    detect-secrets scan --baseline .secrets.baseline
```

---

## 4. Semgrep — Advanced Static Security Scanner

**What it does:** Pattern-based static analysis targeting security vulnerabilities specific to Python and Django (SQL injection, XSS, SSRF, insecure deserialization, etc.).

**Configuration:** [.semgrep.yml](.semgrep.yml)

**Local usage:**

```bash
# Scan using local config
semgrep scan

# Scan using Semgrep Registry rules (recommended for comprehensive coverage)
semgrep scan --config auto

# Django-specific rules only
semgrep scan --config p/django

# OWASP Top 10 rules
semgrep scan --config p/owasp-top-ten

# JSON output
semgrep scan --json -o semgrep-report.json
```

**CI usage:**

```yaml
- name: Semgrep Security Scan
  run: |
    pip install semgrep
    semgrep scan --config auto --json -o semgrep-report.json
```

---

## 5. Trivy — Container & Dependency Vulnerability Scanner

**What it does:** Scans container images, filesystems, and IaC configurations for vulnerabilities, misconfigurations, and exposed secrets.

**Installation:** Trivy is a standalone binary (not a Python package).

```bash
# macOS
brew install trivy

# Linux
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
```

**Local usage:**

```bash
# Filesystem scan (source code + dependencies)
trivy fs .

# Scan the Docker image
trivy image emr-api-dev

# High/Critical only
trivy fs . --severity HIGH,CRITICAL

# JSON output (for CI)
trivy fs . -f json -o trivy-report.json

# Scan Docker image for production
trivy image emr-api-prod --severity HIGH,CRITICAL
```

**CI usage:**

```yaml
- name: Trivy Filesystem Scan
  uses: aquasecurity/trivy-action@master
  with:
    scan-type: 'fs'
    scan-ref: '.'
    severity: 'HIGH,CRITICAL'

- name: Trivy Docker Image Scan
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'emr-api-dev'
    severity: 'HIGH,CRITICAL'
```

---

## 6. SonarQube / SonarCloud — Code Quality & Security

**What it does:** Comprehensive code quality analysis including security hotspots, code smells, duplications, and coverage tracking.

**Configuration:** [sonar-project.properties](sonar-project.properties)

**Local usage (SonarQube):**

```bash
# Start local SonarQube (Docker)
docker run -d --name sonarqube -p 9000:9000 sonarqube:community

# Run scanner (requires sonar-scanner installed)
sonar-scanner \
  -Dsonar.host.url=http://localhost:9000 \
  -Dsonar.token=YOUR_TOKEN
```

**CI usage (SonarCloud):**

```yaml
- name: SonarCloud Scan
  uses: SonarSource/sonarcloud-github-action@master
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

**Prerequisites:**

- Set `sonar.organization` in `sonar-project.properties` for SonarCloud
- Generate coverage report first: `pytest --cov --cov-report=xml:coverage.xml`

---

## 7. Snyk — Dependency Security Monitoring

**What it does:** Continuously monitors project dependencies for known vulnerabilities and provides remediation advice.

**Configuration:** [.snyk](.snyk)

**Installation:**

```bash
npm install -g snyk
snyk auth  # authenticate with Snyk account
```

**Local usage:**

```bash
# Test dependencies for vulnerabilities
snyk test --file=apps/api/requirements.txt --package-manager=pip

# Monitor (sends snapshot to Snyk dashboard)
snyk monitor --file=apps/api/requirements.txt --package-manager=pip

# Scan Docker image
snyk container test emr-api-dev

# IaC scan (docker-compose, etc.)
snyk iac test docker-compose.dev.yml
```

**CI usage:**

```yaml
- name: Snyk Security Scan
  uses: snyk/actions/python@master
  env:
    SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
  with:
    args: --file=apps/api/requirements.txt
```

---

## Security Gate — CI Pipeline

The following commands should run on every PR before allowing a merge. If **any** tool fails, the pipeline fails.

```bash
#!/bin/bash
set -euo pipefail

echo "=== 1. Unit Tests ==="
pytest apps/api/tests/ --tb=short -q

echo "=== 2. Bandit (SAST) ==="
bandit -r apps/api -c .bandit

echo "=== 3. pip-audit (Dependencies) ==="
pip-audit -r apps/api/requirements.txt

echo "=== 4. Semgrep (Advanced SAST) ==="
semgrep scan --config auto --error

echo "=== 5. detect-secrets ==="
detect-secrets scan --baseline .secrets.baseline

echo "=== ALL SECURITY GATES PASSED ==="
```

**GitHub Actions example:**

```yaml
name: Security Gate
on: [pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r apps/api/requirements.txt
          pip install -r apps/api/requirements-dev.txt

      - name: Run tests
        run: pytest apps/api/tests/ --tb=short -q

      - name: Bandit
        run: bandit -r apps/api -c .bandit

      - name: pip-audit
        run: pip-audit -r apps/api/requirements.txt

      - name: Semgrep
        run: semgrep scan --config auto --error

      - name: detect-secrets
        run: detect-secrets scan --baseline .secrets.baseline

      - name: Trivy filesystem
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'HIGH,CRITICAL'
```

---

## File Inventory

| File | Purpose |
|------|---------|
| `apps/api/requirements-dev.txt` | Dev-only Python dependencies (bandit, pip-audit, detect-secrets, semgrep) |
| `.bandit` | Bandit SAST configuration |
| `.semgrep.yml` | Semgrep custom rules + path config |
| `.secrets.baseline` | detect-secrets known-secrets baseline |
| `.snyk` | Snyk vulnerability policy |
| `sonar-project.properties` | SonarQube / SonarCloud project config |
| `SECURITY_TOOLING.md` | This document |

---

## Development Workflow

1. **Install dev dependencies:** `pip install -r apps/api/requirements-dev.txt`
2. **Run scans locally** before pushing (see Quick Reference table)
3. **Regenerate secrets baseline** after adding new config files: `detect-secrets scan > .secrets.baseline`
4. **CI pipeline** runs all security gates automatically on PRs
5. **Review findings** — fix CRITICAL/HIGH immediately, track MEDIUM/LOW in backlog
