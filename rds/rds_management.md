# RDS — Management

## Service Overview

**Amazon RDS** provides managed relational databases (PostgreSQL, MySQL, Aurora). Common in data engineering for operational data stores, metadata, and CDC sources.

---

## AWS CLI Commands

### Create DB Instance

```bash
aws rds create-db-instance \
  --db-instance-identifier analytics-metadata \
  --db-instance-class db.r6g.large \
  --engine postgres \
  --engine-version 15.4 \
  --master-username admin \
  --master-user-password 'CHANGE_ME' \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --vpc-security-group-ids sg-0abc123 \
  --db-subnet-group-name data-platform-db-subnet \
  --backup-retention-period 7 \
  --no-publicly-accessible
```

### Describe DB Instances

```bash
aws rds describe-db-instances \
  --query 'DBInstances[].{ID:DBInstanceIdentifier,Engine:Engine,Status:DBInstanceStatus,Endpoint:Endpoint.Address}' \
  --output table
```

### Reboot Instance

```bash
aws rds reboot-db-instance --db-instance-identifier analytics-metadata
```

### Modify Instance

```bash
aws rds modify-db-instance \
  --db-instance-identifier analytics-metadata \
  --db-instance-class db.r6g.xlarge \
  --apply-immediately
```

---

## Advanced Commands

### Create Read Replica

```bash
aws rds create-db-instance-read-replica \
  --db-instance-identifier analytics-metadata-replica \
  --source-db-instance-identifier analytics-metadata
```

---

## Python (Boto3) Examples

```python
import boto3

rds = boto3.client("rds")

def wait_for_available(db_id: str) -> None:
    waiter = rds.get_waiter("db_instance_available")
    waiter.wait(DBInstanceIdentifier=db_id)
```

---

## Security Considerations

- Store credentials in **Secrets Manager** with automatic rotation.
- Use **private subnets** only; security groups limited to ETL CIDRs.
- Enable **Performance Insights** and **Enhanced Monitoring**.

---

## Best Practices

- Use **Aurora** for high-throughput analytics ingestion.
- Enable **Multi-AZ** for production OLTP sources.
- Export snapshots to S3 for **Glue/Athena** analytics on RDS data.
