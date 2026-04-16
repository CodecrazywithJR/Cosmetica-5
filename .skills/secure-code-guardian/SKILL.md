---
name: secure-code-guardian
description: Use when implementing authentication/authorization, securing user input, or preventing OWASP Top 10 vulnerabilities — including custom security implementations such as hashing passwords with bcrypt/argon2, sanitizing SQL queries with parameterized statements, configuring CORS/CSP headers, validating input with Zod, and setting up JWT tokens.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.0"
  domain: security
  triggers: security, authentication, authorization, encryption, OWASP, vulnerability, secure coding, password, JWT, OAuth
  role: specialist
  scope: implementation
  output-format: code
  related-skills: fullstack-guardian, security-reviewer, architecture-designer
---

# Secure Code Guardian

## Core Workflow

1. **Threat model** — Identify attack surface and threats
2. **Design** — Plan security controls
3. **Implement** — Write secure code with defense in depth
4. **Validate** — Test security controls with explicit checkpoints
5. **Document** — Record security decisions

### Validation Checkpoints

After each implementation step, verify:

- **Authentication**: Test brute-force protection (lockout/rate limit triggers), session fixation resistance, token expiration, and invalid-credential error messages (must not leak user existence).
- **Authorization**: Verify horizontal and vertical privilege escalation paths are blocked; test with tokens belonging to different roles/users.
- **Input handling**: Confirm SQL injection payloads (`' OR 1=1--`) are rejected; confirm XSS payloads (`<script>alert(1)</script>`) are escaped or rejected.
- **Headers/CORS**: Validate with a security scanner (e.g., `curl -I`, Mozilla Observatory) that security headers are present and CORS origin allowlist is correct.

## Constraints

### MUST DO
- Hash passwords with bcrypt/argon2 (never MD5/SHA-1/unsalted hashes)
- Use parameterized queries (never string-interpolated SQL)
- Validate and sanitize all user input before use
- Implement rate limiting on auth endpoints
- Set security headers (CSP, HSTS, X-Frame-Options)
- Log security events (failed auth, privilege escalation attempts)
- Store secrets in environment variables or secret managers (never in source code)

### MUST NOT DO
- Store passwords in plaintext or reversibly encrypted form
- Trust user input without validation
- Expose sensitive data in logs or error responses
- Use weak or deprecated algorithms (MD5, SHA-1, DES, ECB mode)
- Hardcode secrets or credentials in code

## Code Examples

### Password Hashing (bcrypt)
```typescript
import bcrypt from 'bcrypt';

const SALT_ROUNDS = 12;

export async function hashPassword(plaintext: string): Promise<string> {
  return bcrypt.hash(plaintext, SALT_ROUNDS);
}

export async function verifyPassword(plaintext: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plaintext, hash);
}
```

### Parameterized SQL Query (Node.js / pg)
```typescript
// NEVER: `SELECT * FROM users WHERE email = '${email}'`
// ALWAYS: use positional parameters
import { Pool } from 'pg';
const pool = new Pool();

export async function getUserByEmail(email: string) {
  const { rows } = await pool.query(
    'SELECT id, email, role FROM users WHERE email = $1',
    [email]
  );
  return rows[0] ?? null;
}
```

### Input Validation with Zod
```typescript
import { z } from 'zod';

const LoginSchema = z.object({
  email: z.string().email().max(254),
  password: z.string().min(8).max(128),
});

export function validateLoginInput(raw: unknown) {
  const result = LoginSchema.safeParse(raw);
  if (!result.success) {
    throw new Error('Invalid credentials format');
  }
  return result.data;
}
```

### JWT Validation
```typescript
import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET!;

export function verifyToken(token: string): jwt.JwtPayload {
  const payload = jwt.verify(token, JWT_SECRET, {
    algorithms: ['HS256'],
    issuer: 'your-app',
    audience: 'your-app',
  });
  if (typeof payload === 'string') throw new Error('Invalid token payload');
  return payload;
}
```

### Securing an Endpoint — Full Flow
```typescript
import express from 'express';
import rateLimit from 'express-rate-limit';
import helmet from 'helmet';

const app = express();
app.use(helmet());
app.use(express.json({ limit: '10kb' }));

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
});

app.post('/api/login', authLimiter, async (req, res) => {
  const { email, password } = validateLoginInput(req.body);

  const user = await getUserByEmail(email);
  if (!user || !(await verifyPassword(password, user.passwordHash))) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const token = jwt.sign(
    { sub: user.id, role: user.role },
    JWT_SECRET,
    { algorithm: 'HS256', expiresIn: '15m', issuer: 'your-app', audience: 'your-app' }
  );

  res.cookie('token', token, { httpOnly: true, secure: true, sameSite: 'strict' });
  return res.json({ message: 'Authenticated' });
});
```

## Output Templates

When implementing security features, provide:
1. Secure implementation code
2. Security considerations noted
3. Configuration requirements (env vars, headers)
4. Testing recommendations

## Knowledge Reference

OWASP Top 10, bcrypt/argon2, JWT, OAuth 2.0, OIDC, CSP, CORS, rate limiting, input validation, output encoding, encryption (AES, RSA), TLS, security headers
