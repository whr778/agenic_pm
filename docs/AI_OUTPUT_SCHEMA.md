# Structured AI Output Schema Proposal (Part 9)

## Goal

Define one strict JSON shape returned by the AI that always includes a user-facing message and may include board updates.

## Design principles

- Keep parsing simple and deterministic.
- Allow no-op responses (message only).
- Validate all update operations before applying.
- Reject malformed output with clear backend error handling.

## Proposed response shape

```json
{
  "assistantMessage": "string",
  "updates": [
    {
      "type": "rename_board",
      "boardName": "string"
    },
    {
      "type": "rename_column",
      "columnId": "123",
      "title": "string"
    },
    {
      "type": "create_card",
      "columnId": "123",
      "title": "string",
      "details": "string"
    },
    {
      "type": "update_card",
      "cardId": "456",
      "title": "string",
      "details": "string"
    },
    {
      "type": "delete_card",
      "cardId": "456"
    },
    {
      "type": "move_card",
      "cardId": "456",
      "toColumnId": "124",
      "toIndex": 0
    }
  ]
}
```

## Validation rules

- `assistantMessage`
  - required
  - non-empty string after trim
- `updates`
  - optional array
  - defaults to empty array when omitted
- IDs
  - numeric strings only (`"123"`)
- `rename_board`
  - `boardName` required, non-empty
- `rename_column`
  - `columnId`, `title` required
- `create_card`
  - `columnId`, `title` required
  - `details` optional, defaults to empty string
- `update_card`
  - `cardId`, `title` required
  - `details` optional, defaults to empty string
- `delete_card`
  - `cardId` required
- `move_card`
  - `cardId`, `toColumnId`, `toIndex` required
  - `toIndex >= 0`

## Application behavior

- Backend processes `updates` in array order.
- All updates execute in one DB transaction.
- If any operation fails validation or lookup, transaction is rolled back.
- API still returns a safe assistant message and an error payload describing why updates were rejected.

## Prompting guidance

- Backend will provide:
  - current board JSON snapshot
  - conversation history
  - user prompt
- Backend will instruct the model to return JSON only and conform exactly to this schema.

## Suggested backend response to frontend

```json
{
  "assistantMessage": "string",
  "appliedUpdates": true,
  "updateCount": 2,
  "board": {
    "boardId": "1",
    "name": "Main Board",
    "columns": [],
    "cards": {}
  }
}
```

## Open questions for approval

- Is operation ordering as-provided by the AI acceptable?
- Should partial update application ever be allowed (currently no; all-or-nothing)?
- Is this operation set complete for MVP?
