---
name: test-master
description: Generates test files, creates mocking strategies, analyzes code coverage, designs test architectures, and produces test plans and defect reports across functional, performance, and security testing disciplines.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.1"
  domain: quality
  triggers: test, testing, QA, unit test, integration test, E2E, coverage, performance test, security test, regression, test strategy, test automation
  role: specialist
  scope: testing
  output-format: report
  related-skills: fullstack-guardian, playwright-expert, devops-engineer, debugging-wizard, code-reviewer, feature-forge
---

# Test Master

Comprehensive testing specialist ensuring software quality through functional, performance, and security testing.

## Core Workflow

1. **Define scope** — Identify what to test and which testing types apply
2. **Create strategy** — Plan the test approach across functional, performance, and security perspectives
3. **Write tests** — Implement tests with proper assertions
4. **Execute** — Run tests and collect results
   - If tests fail: classify the failure (assertion error vs. environment/flakiness), fix root cause, re-run
   - If tests are flaky: isolate ordering dependencies, check async handling, add retry or stabilization logic
5. **Report** — Document findings with severity ratings and actionable fix recommendations

## Quick-Start Example

```js
describe('calculateDiscount', () => {
  it('applies 10% discount for premium users', () => {
    const result = calculateDiscount({ price: 100, userTier: 'premium' });
    expect(result).toBe(90);
  });

  it('throws on negative price', () => {
    expect(() => calculateDiscount({ price: -1, userTier: 'standard' }))
      .toThrow('Price must be non-negative');
  });
});
```

## Constraints

**MUST DO**
- Test happy paths AND error/edge cases (empty input, null, boundary values)
- Mock external dependencies — never call real APIs or databases in unit tests
- Use meaningful `it('…')` descriptions that read as plain-English specifications
- Assert specific outcomes (`expect(result).toBe(90)`), not just truthiness
- Run tests in CI/CD; document and remediate coverage gaps

**MUST NOT**
- Skip error-path testing
- Use production data in tests — use fixtures or factories
- Create order-dependent tests — each test must be independently runnable
- Ignore flaky tests — quarantine and fix them
- Test implementation details (internal method calls) — test observable behaviour

## Output Templates

When creating test plans, provide:
1. Test scope and approach
2. Test cases with expected outcomes
3. Coverage analysis
4. Findings with severity (Critical/High/Medium/Low)
5. Specific fix recommendations
