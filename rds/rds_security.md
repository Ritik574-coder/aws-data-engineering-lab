# RDS — Security

## Service Overview

RDS security covers network isolation, encryption, IAM database authentication, and Secrets Manager integration.

---

## AWS CLI Commands

### Enable Encryption (at creation)

```bash
aws rds create-db-instance ... --storage-encrypted --kms-key-id alias/rds-key
```

### Modify Security Groups

```bash
aws rds modify-db-instance \
  --db-instance-identifier analytics-metadata \
  --vpc-security-group-ids sg-new123 \
  --apply-immediately
```

### Enable IAM Database Authentication

```bash
aws rds modify-db-instance \
  --db-instance-identifier analytics-metadata \
  --enable-iam-database-authentication \
  --apply-immediately
```

---

## Security Considerations

- Rotate master passwords via **Secrets Manager**.
- Restrict SG ingress to **Glue connection** security groups only.
- Enable **deletion protection** on production instances.

---

## Troubleshooting

| Error | Resolution |
|-------|------------|
| Connection timeout | Check SG, NACL, and subnet routing |
| SSL required | Use `sslmode=require` in connection strings |
