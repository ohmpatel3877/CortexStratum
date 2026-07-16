# Skill: security-hardening

# Security Hardening — Defense in Depth Expert

## Security Layers (from outermost to innermost)

### Layer 1: Network Security
- TLS 1.3 minimum, disable TLS 1.0/1.1
- HSTS headers with includeSubDomains
- Network segmentation (DMZ, internal, database tiers)
- Rate limiting at proxy/load balancer

### Layer 2: Application Security (OWASP Top 10)
1. Broken Access Control → RBAC, least privilege, deny-by-default
2. Cryptographic Failures → Use modern algorithms (AES-256-GCM, Argon2id), never roll your own
3. Injection → Parameterized queries, input validation whitelist, output encoding
4. Insecure Design → Threat modeling at design phase, STRIDE per feature
5. Security Misconfiguration → CIS benchmarks, automated config scanning
6. Vulnerable Components → SBOM, dependency scanning, automated updates
7. Auth Failures → MFA, session rotation, secure cookie flags
8. Data Integrity Failures → Signatures, checksums, audit trails
9. Logging Failures → Centralized logging, never log secrets, alert on anomalies
10. SSRF → URL allowlists, disable localhost access, validate redirects

### Layer 3: Data Security
- At rest: AES-256 encryption, key rotation, HSM for master keys
- In transit: TLS 1.3, certificate pinning for critical services
- In use: Memory encryption for sensitive data, zero-copy where possible

### Layer 4: Identity & Access
- Authentication: OAuth 2.0 / OIDC, MFA enforced for admin
- Authorization: ABAC for fine-grained, RBAC for coarse-grained
- Session management: Short-lived JWTs, refresh token rotation, secure cookie flags

### Layer 5: Supply Chain
- Dependency scanning (npm audit, cargo audit, pip audit)
- SBOM generation (CycloneDX format)
- Artifact signing and verification

## Automated Checks (run these)
1. `python scripts/security-scan.py --dir .` — full security scan
2. Check for .env files committed to git
3. Verify CSP headers in config
4. Check for hardcoded secrets
5. Verify TLS config
6. Check dependency vulnerabilities

## Incident Response (follow xTrace flow)
1. Detect → Log to xTrace via error-trace.ps1
2. Triage → Categorize severity
3. Contain → Isolate affected component
4. Eradicate → Apply fix
5. Recover → Verify fix, restore from clean backup
6. Postmortem → Log root cause in DTrace, store in NE-Memory
