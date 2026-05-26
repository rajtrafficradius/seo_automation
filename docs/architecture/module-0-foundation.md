# Module 0 Foundation

Module 0 is the first implemented slice of the system and owns:

- onboarding input intake
- CDD upload and extraction
- website/domain normalization
- site classification
- SEMrush intelligence collection
- initial keyword universe assembly
- quick win detection
- URL architecture map generation

## Frontend Responsibilities

- collect structured business fields
- accept a single CDD upload
- submit multipart form data to the API
- present Module 0 result objects

## Backend Responsibilities

- validate request payloads
- parse CDD uploads across supported formats
- normalize project identity
- orchestrate Module 0 services
- return stable typed responses

## Deferred

- auth and RBAC
- background jobs
- RLS-enforced persistence flows
- production SEMrush throttling strategy
- AI SOV, fan-out, and entity baseline production logic
