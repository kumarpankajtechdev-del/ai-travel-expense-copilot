# AWS Deployment Notes

A production deployment can split this service into event-driven components:

- API Gateway for claim submission and receipt parse APIs
- AWS Lambda for synchronous claim review
- Step Functions for long-running approval workflows
- SQS for reviewer queue and retry handling
- SNS for approval and rejection notifications
- S3 for receipt storage
- RDS or DynamoDB for operational claim data
- ClickHouse on EC2 or ClickHouse Cloud for analytics

Suggested flow:

1. API Gateway receives claim request.
2. Lambda validates request and stores receipt metadata.
3. Step Functions runs parse, retrieve policy, evaluate, and notify steps.
4. SQS queues claims that require human review.
5. ClickHouse receives claim events for analytics.
