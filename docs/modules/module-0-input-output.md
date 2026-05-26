# Module 0 Input and Output Contract

## Inputs

- website URL
- optional domain override
- target country
- brand name
- business type
- services or products
- target locations
- business goals
- priority services
- known competitors optional
- excluded services/pages optional
- brand profiles optional
- notes optional
- CDD upload file

## Output Buckets

- normalized project metadata
- CDD extraction summary
- site classification
- SEMrush status
- SEMrush data source metadata
- SEMrush fallback warning when applicable
- keyword universe preview
- quick wins preview
- TAM summary
- URL architecture preview
- next-step notes

## SEMrush Runtime Rules

- Always try real SEMrush first when `SEMRUSH_API_KEY` is available.
- If SEMrush fails because of credits, quota, 403, timeout, empty response, or API access errors, use estimated fallback data for that run.
- If `OPENAI_API_KEY` is available, use OpenAI first for estimated fallback keyword generation.
- Estimated OpenAI fallback runs should be labeled with `data_source = openai_mock_fallback`, `fallback_used = true`, `is_estimated = true`, and `status = credits_unavailable` when credits are unavailable.
- Use `MODULE0_FORCE_MOCK_SEMRUSH=true` only when you explicitly want to force fallback mode during testing.
- If OpenAI is unavailable or fails, fall back to deterministic synthetic data as the final fallback layer.
- When SEMrush becomes available again, automatically return to real SEMrush data without code changes.
- In test and development mode, limit the keyword universe using `MODULE0_TEST_KEYWORD_LIMIT`.
