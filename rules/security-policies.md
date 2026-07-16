# Security Policies — Mandatory Rules for Code Generation

## Authentication & Authorization
- ALWAYS use parameterized queries for database operations (never string interpolation)
- ALWAYS hash passwords with Argon2id or bcrypt (never MD5, SHA1, or plain SHA256)
- ALWAYS use constant-time comparison for secret verification
- ALWAYS validate JWT signatures and expiry on every request
- ALWAYS implement rate limiting on auth endpoints

## Data Validation
- ALWAYS whitelist-validate user input (reject unknown, don't just filter known-bad)
- ALWAYS use Content-Type headers to enforce expected payload formats
- ALWAYS encode output based on context (HTML entity, URL, JavaScript, etc.)
- NEVER use eval(), exec(), or similar dynamic code execution with user input

## Secrets & Configuration
- NEVER hardcode secrets — use environment variables or a secrets manager
- ALWAYS use short-lived credentials with automatic rotation
- ALWAYS set Secure, HttpOnly, SameSite=Strict on session cookies
- ALWAYS implement Content Security Policy headers with restrictive defaults

## Communication
- ALWAYS use TLS 1.3 for all network communication
- ALWAYS verify TLS certificates (never disable verification)
- ALWAYS validate redirect URLs to prevent open redirect vulnerabilities

## Logging & Monitoring
- NEVER log passwords, tokens, or PII
- ALWAYS log security-relevant events (auth failures, permission changes, data access)
- ALWAYS use structured logging for machine-parsable security events
