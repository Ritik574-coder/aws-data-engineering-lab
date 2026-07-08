# Lake Formation — Data Lake Governance

## Service Overview

**AWS Lake Formation** provides centralized governance for data lakes built on S3. It integrates with AWS Glue Data Catalog to manage databases, tables, and fine-grained access control (LF-TBAC) using tags and cell-level security.

**Common use cases:**
- Grant analysts SELECT on curated tables without S3 bucket-wide access
- Enforce column-level masking for PII in shared data products
- Register S3 locations and manage data lake permissions across accounts
- Audit data access via CloudTrail LF API calls

**When to use it:** When multiple teams share a data lake and you need catalog-level permissions finer than IAM S3 policies — especially for Athena, Redshift Spectrum, and EMR.

---

## AWS CLI Commands

### Register S3 Location

**Purpose:** Register a data lake S3 prefix with Lake Formation.

**Command:**

```bash
aws lakeformation register-resource \
  --resource-arn arn:aws:s3:::my-data-lake-curated \
  --use-service-linked-role
```

**With custom role:**

```bash
aws lakeformation register-resource \
  --resource-arn arn:aws:s3:::my-data-lake-curated/orders/ \
  --role-arn arn:aws:iam::123456789012:role/LakeFormationDataAccessRole
```

---

### Grant Database Permissions

**Purpose:** Allow a data analyst role to describe and list tables in a database.

**Command:**

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::123456789012:role/DataAnalystRole"}' \
  --resource '{"Database": {"Name": "analytics_curated"}}' \
  --permissions DESCRIBE CREATE_TABLE ALTER
```

---

### Grant Table SELECT

**Purpose:** Allow querying a specific table via Athena.

**Command:**

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::123456789012:role/DataAnalystRole"}' \
  --resource '{"Table": {"DatabaseName": "analytics_curated", "Name": "orders"}}' \
  --permissions SELECT DESCRIBE
```

---

### Grant Column-Level Access

**Purpose:** Restrict access to non-PII columns only.

**Command:**

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::123456789012:role/DataAnalystRole"}' \
  --resource '{
    "TableWithColumns": {
      "DatabaseName": "analytics_curated",
      "Name": "customers",
      "ColumnNames": ["customer_id", "region", "segment"]
    }
  }' \
  --permissions SELECT
```

---

### List Permissions

```bash
aws lakeformation list-permissions \
  --resource '{"Database": {"Name": "analytics_curated"}}'
```

---

### Revoke Permissions

```bash
aws lakeformation revoke-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::123456789012:role/FormerAnalystRole"}' \
  --resource '{"Table": {"DatabaseName": "analytics_curated", "Name": "orders"}}' \
  --permissions SELECT DESCRIBE
```

---

### Create LF-Tag

**Purpose:** Tag-based access control for multi-tenant data lakes.

**Command:**

```bash
aws lakeformation create-lf-tag \
  --tag-key Environment \
  --tag-values production staging dev

aws lakeformation create-lf-tag \
  --tag-key DataDomain \
  --tag-values orders customers finance
```

---

### Assign LF-Tags to Database

```bash
aws lakeformation add-lf-tags-to-resource \
  --resource '{"Database": {"Name": "analytics_curated"}}' \
  --lf-tags Environment=production DataDomain=orders
```

---

### Grant Permissions via LF-Tags

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::123456789012:role/OrdersAnalystRole"}' \
  --resource '{"LFTagPolicy": {"ResourceType": "TABLE", "Expression": [{"TagKey": "DataDomain", "TagValues": ["orders"]}]}}' \
  --permissions SELECT DESCRIBE
```

---

### Get Data Lake Settings

```bash
aws lakeformation get-data-lake-settings
```

**Purpose:** View admins, default permissions, and trusted resource owners.

---

## Advanced Commands

### Cross-Account Sharing

```bash
# Producer account: grant permissions to consumer account
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "123456789012"}' \
  --resource '{"Database": {"Name": "shared_analytics"}}' \
  --permissions DESCRIBE
```

### Data Cells Filter (Row-Level Security)

```bash
aws lakeformation create-data-cells-filter \
  --table-data '{"DatabaseName": "analytics_curated", "TableName": "orders", "Name": "us-orders-only"}' \
  --column-names order_id amount region order_date \
  --row-filter '{"FilterType": "CUSTOM", "Expression": "region = '\''US'\''"}'
```

### Batch Grant Permissions

```bash
aws lakeformation batch-grant-permissions \
  --entries file://grant-batch.json
```

### Search Databases by LF-Tag

```bash
aws lakeformation search-databases-by-lf-tags \
  --expression '[{"TagKey": "Environment", "TagValues": ["production"]}]'
```

---

## Python Boto3 Examples

See [lake_formation_python_examples.md](lake_formation_python_examples.md).

---

## Security Considerations

- Designate **Lake Formation admins** carefully — they can grant any permission in the catalog.
- Disable **IAMAllowedPrincipals** default grants when enforcing LF-only access (`PutDataLakeSettings`).
- Combine LF permissions with **S3 bucket policies** — LF governs catalog access; S3 still needs aligned policies.
- Use **LF-Tags** for scalable multi-team governance instead of per-table grants.
- Enable **CloudTrail** for `GrantPermissions`, `RevokePermissions`, and `BatchGrantPermissions`.
- Apply **column masking** and **row filters** for regulated data (HIPAA, GDPR).

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `AccessDeniedException` in Athena | Missing LF SELECT on table/database | Grant DESCRIBE + SELECT; check IAMAllowedPrincipals |
| `Insufficient Lake Formation permissions` | Caller is not LF admin | Add user/role to data lake admins |
| Table visible but query fails | S3 location not registered | Register S3 path; verify data access role |
| Cross-account query fails | RAM share not configured | Share database via Lake Formation; accept in consumer account |
| `InvalidInputException` on tags | Tag key/value mismatch | Verify tag exists with `ListLFTags` |

---

## Best Practices

- **Register all data lake S3 prefixes** under Lake Formation management early.
- **Use LF-Tags** (`Environment`, `DataDomain`, `Sensitivity`) for consistent policy application.
- **Revoke IAMAllowedPrincipals** once LF policies are validated — prevents bypass via IAM-only S3 access.
- **Automate grants** in CI/CD when new curated tables are published.
- **Audit permissions quarterly** with `list-permissions` and Access Analyzer.
- **Separate raw and curated zones** with different LF-Tags and stricter policies on curated data.
- **Document data products** — tie LF-Tags to catalog metadata for discoverability.
