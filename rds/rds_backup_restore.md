# RDS — Backup & Restore

## Service Overview

RDS automated backups, manual snapshots, and point-in-time recovery protect operational data used in pipelines.

---

## AWS CLI Commands

### Create Manual Snapshot

```bash
aws rds create-db-snapshot \
  --db-snapshot-identifier analytics-metadata-snap-20250301 \
  --db-instance-identifier analytics-metadata
```

### Restore from Snapshot

```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier analytics-metadata-restored \
  --db-snapshot-identifier analytics-metadata-snap-20250301 \
  --db-subnet-group-name data-platform-db-subnet \
  --no-publicly-accessible
```

### Point-in-Time Restore

```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier analytics-metadata \
  --target-db-instance-identifier analytics-metadata-pitr \
  --restore-time 2025-03-01T12:00:00Z
```

### Export Snapshot to S3 (Parquet)

```bash
aws rds start-export-task \
  --export-task-identifier export-analytics-20250301 \
  --source-arn arn:aws:rds:us-east-1:123456789012:snapshot:analytics-metadata-snap \
  --s3-bucket-name my-data-lake-raw \
  --s3-prefix rds-exports/analytics/ \
  --iam-role-arn arn:aws:iam::123456789012:role/RDSExportRole \
  --kms-key-id alias/data-lake-key
```

---

## Best Practices

- Test restore procedures **monthly**.
- Use **AWS Backup** for cross-region snapshot copies.
- Export to S3 for **data lake integration** and Athena queries.
