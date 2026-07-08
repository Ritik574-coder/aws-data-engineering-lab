# IAM — Security Best Practices

## Overview

Production IAM hygiene for data engineering teams — covering identity federation, least privilege, auditing, and credential management.

---

## Core Principles

1. **No long-lived root credentials** — enable MFA on root; use it only for account-level tasks.
2. **Roles over users** — Lambda, Glue, EC2, and CI/CD should use IAM roles.
3. **SSO for humans** — AWS IAM Identity Center with group-to-permission-set mapping.
4. **Least privilege** — scope to specific ARNs and prefixes.
5. **Permission boundaries** — cap maximum permissions for developer roles.

---

## AWS CLI Commands

### Generate Credential Report

```bash
aws iam generate-credential-report
aws iam get-credential-report --query 'Content' --output text | base64 -d > credential-report.csv
```

### Enable MFA Device (virtual)

```bash
aws iam create-virtual-mfa-device --virtual-mfa-device-name admin-mfa
```

### List Access Keys (Audit)

```bash
aws iam list-access-keys --user-name etl-service-user
```

### Get Account Password Policy

```bash
aws iam get-account-password-policy
```

---

## Security Checklist

| Control | Command / Tool |
|---------|----------------|
| Unused credentials | Credential report + `last_used` |
| Overprivileged policies | Access Analyzer |
| Public resource exposure | Access Analyzer external access |
| MFA enforcement | IAM password policy + SSO |
| Cross-account access | ExternalId in trust policies |

---

## Python (Boto3) — Audit Stale Access Keys

```python
import csv
import io
import boto3
from datetime import datetime, timezone, timedelta

iam = boto3.client("iam")

def find_stale_keys(max_age_days: int = 90) -> list[str]:
    iam.generate_credential_report()
    report = iam.get_credential_report()["Content"].decode("utf-8")
    reader = csv.DictReader(io.StringIO(report))
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stale = []
    for row in reader:
        for i in ("1", "2"):
            if row.get(f"access_key_{i}_active") == "true":
                last_used = row.get(f"access_key_{i}_last_used_date", "N/A")
                if last_used == "N/A":
                    stale.append(row["user"])
    return stale
```

---

## Troubleshooting

- **Privilege escalation paths** — review `iam:PassRole`, `sts:AssumeRole`, and `lambda:CreateFunction`.
- **Confused deputy** — always use `ExternalId` for third-party cross-account access.

---

## Best Practices

- Rotate secrets via **Secrets Manager**; never in environment variables in code repos.
- Use **SCP**s in Organizations to deny dangerous actions account-wide.
- Tag all identities for **cost and ownership** tracking.
- Review IAM quarterly with automated tooling (Prowler, Steampipe, IAM Access Analyzer).
