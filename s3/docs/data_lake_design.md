# Production Data Lake Design on S3

This document explains how to design S3 object layouts for data engineering.

## Layers

Bronze stores raw immutable data. Silver stores cleaned and standardized data.
Gold stores business-ready aggregates, marts, and serving datasets.

## Naming Convention

Use predictable keys:

```text
bronze/<domain>/<dataset>/year=YYYY/month=MM/day=DD/<file>
silver/<domain>/<dataset>/year=YYYY/month=MM/day=DD/<file>
gold/<domain>/<dataset>/year=YYYY/month=MM/day=DD/<file>
```

## File Formats

Use compressed JSON Lines or Parquet for bronze depending on ingestion
requirements. Use Snappy Parquet for silver and gold analytics. Consider table
formats such as Iceberg, Delta Lake, or Hudi for transactional data lakes.

## Partitioning

Partition by query predicates, not by habit. Date partitions are common, but
customer, region, event type, or tenant can be better when they match query
filters. Avoid high-cardinality partitions that create tiny files.

## Compression

Compression reduces storage and scan cost. Snappy balances speed and size for
analytics. Gzip can be useful for raw logs but is less splittable for distributed
processing.

## Security

Separate sensitive domains by bucket or prefix with clear policies. Use SSE-KMS
for regulated data. Use Lake Formation, IAM, Access Points, or bucket policies
for access boundaries.

## Pricing

Small files increase request cost and query overhead. Old versions, incomplete
multipart uploads, and unexpired temporary data create hidden cost. Inventory
and lifecycle rules are core governance tools.

## Performance

Use multipart uploads for large files. Compact small files. Prefer columnar
formats. Keep object sizes appropriate for the query engine, often hundreds of
MBs for analytical Parquet objects.

## Production Recommendations

- Make raw ingestion immutable.
- Use deterministic key builders like `DataLakeObjectKey`.
- Validate schemas before writing silver and gold layers.
- Track lineage and quality metrics.
- Use lifecycle policies for temporary and historical data.

