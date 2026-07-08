# Lake Formation — Python Boto3 Examples

## Service Overview

The Boto3 `lakeformation` client manages data lake permissions, LF-Tags, resource registration, and row/column security programmatically.

---

## Basic Examples

### Session and Client

```python
import boto3

session = boto3.Session(profile_name="data-engineer", region_name="us-east-1")
lf = session.client("lakeformation")
```

### Grant Table SELECT

```python
lf.grant_permissions(
    Principal={"DataLakePrincipalIdentifier": "arn:aws:iam::123456789012:role/DataAnalystRole"},
    Resource={
        "Table": {
            "DatabaseName": "analytics_curated",
            "Name": "orders",
        }
    },
    Permissions=["SELECT", "DESCRIBE"],
)
```

### Register S3 Location

```python
lf.register_resource(
    ResourceArn="arn:aws:s3:::my-data-lake-curated/orders/",
    UseServiceLinkedRole=True,
)
```

---

## Production-Ready Examples

### Onboard New Curated Table

```python
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

DATABASE = "analytics_curated"
TABLE = "orders_daily"
ANALYST_ROLE = "arn:aws:iam::123456789012:role/DataAnalystRole"
S3_PREFIX = "arn:aws:s3:::my-data-lake-curated/orders/"


def onboard_table(lf_client) -> None:
    lf_client.register_resource(ResourceArn=S3_PREFIX, UseServiceLinkedRole=True)

    lf_client.grant_permissions(
        Principal={"DataLakePrincipalIdentifier": ANALYST_ROLE},
        Resource={"Database": {"Name": DATABASE}},
        Permissions=["DESCRIBE"],
    )

    lf_client.grant_permissions(
        Principal={"DataLakePrincipalIdentifier": ANALYST_ROLE},
        Resource={"Table": {"DatabaseName": DATABASE, "Name": TABLE}},
        Permissions=["SELECT", "DESCRIBE"],
    )

    lf_client.add_lf_tags_to_resource(
        Resource={"Table": {"DatabaseName": DATABASE, "Name": TABLE}},
        LFTags={"Environment": ["production"], "DataDomain": ["orders"]},
    )
    logger.info("Onboarded %s.%s", DATABASE, TABLE)
```

### Batch Grant from Config

```python
from typing import Iterable


def batch_grant_select(
    lf_client,
    database: str,
    tables: Iterable[str],
    principal_arn: str,
) -> None:
    entries = [
        {
            "Id": f"{database}-{table}",
            "Principal": {"DataLakePrincipalIdentifier": principal_arn},
            "Resource": {
                "Table": {"DatabaseName": database, "Name": table},
            },
            "Permissions": ["SELECT", "DESCRIBE"],
        }
        for table in tables
    ]

    response = lf_client.batch_grant_permissions(Entries=entries)
    failures = response.get("Failures", [])
    if failures:
        raise RuntimeError(f"Batch grant failures: {failures}")
```

### Audit Table Permissions

```python
def list_table_grants(lf_client, database: str, table: str) -> list[dict]:
    response = lf_client.list_permissions(
        Resource={
            "Table": {"DatabaseName": database, "Name": table},
        }
    )
    grants = []
    for entry in response.get("PrincipalResourcePermissions", []):
        grants.append({
            "principal": entry["Principal"].get("DataLakePrincipalIdentifier"),
            "permissions": entry.get("Permissions", []),
        })
    return grants
```

### Disable IAM-Only Fallback

```python
def enforce_lf_only(lf_client, admin_arns: list[str]) -> None:
    lf_client.put_data_lake_settings(
        DataLakeSettings={
            "DataLakeAdmins": [{"DataLakePrincipalIdentifier": arn} for arn in admin_arns],
            "CreateDatabaseDefaultPermissions": [],
            "CreateTableDefaultPermissions": [],
        }
    )
```

---

## Error Handling

```python
from botocore.exceptions import ClientError

try:
    lf.grant_permissions(
        Principal={"DataLakePrincipalIdentifier": "arn:aws:iam::123456789012:role/Analyst"},
        Resource={"Table": {"DatabaseName": "db", "Name": "tbl"}},
        Permissions=["SELECT"],
    )
except ClientError as exc:
    code = exc.response["Error"]["Code"]
    if code == "InvalidInputException":
        print("Check principal ARN and resource name")
    elif code == "AccessDeniedException":
        print("Caller must be a Lake Formation admin")
    else:
        raise
```

---

## Security Considerations

- Run permission changes with an admin role — never embed admin credentials in pipeline code.
- Log all grant/revoke operations for compliance audit trails.
- Validate principal ARNs before batch grants to avoid accidental cross-team access.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Athena still denied after grant | Wait for catalog propagation; verify DESCRIBE on database |
| Batch partial failure | Inspect `Failures` in response; retry failed entry IDs |
| Tag grant not applied | Confirm LF-Tags assigned to resource with `GetResourceLFTags` |

---

## Best Practices

- Encapsulate grant logic in a reusable module called from table-deployment pipelines.
- Use idempotent checks — `list_permissions` before granting to avoid duplicate entries.
- Tag all automated grants with a pipeline identifier in CloudTrail via role session names.
