# Profile Backend Contract

Internal engineering document for the FastAPI backend implementation.

---

## Authentication

The backend must authenticate users via Firebase ID tokens.

### Token Verification

1. The frontend sends the Firebase ID token in the `Authorization` header as `Bearer <token>`.
2. The backend verifies the token using Firebase Admin SDK.
3. The backend extracts the authenticated Firebase UID from the verified token.
4. The backend uses this UID for all Firestore operations.

### Critical Security Requirement

**Never trust a client-provided UID.** The UID must come exclusively from a verified Firebase ID token.

```
Authorization: Bearer <firebase_id_token>
```

The backend must reject any request without a valid token.

---

## User Context

The backend needs to retrieve the following data to construct the AI context:

### Coffee Preferences

Location: `users/{uid}/preferences/current`

```typescript
{
  coffee: {
    favoriteDrink: string;
    temperature: "hot" | "iced" | "either";
    milkPreference: string;
    sweetness: string;
    strength: string;
    caffeinePreference: string;
    roastPreference: string;
    brewMethod: string;
    dietaryPreference: string[];
    allergiesOrIntolerances: string;
  }
}
```

### AI Context

Location: `users/{uid}/preferences/current`

```typescript
{
  aiContext: {
    customContext: string;
    responseStyle: "short" | "balanced" | "detailed";
    tone: "friendly" | "casual" | "professional" | "playful";
    recommendationStyle: "best" | "few" | "explain";
    usePreferencesInConversations: boolean;
  }
}
```

### User Memories

Location: `users/{uid}/memories/{memoryId}`

```typescript
{
  text: string;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}
```

---

## Required API Endpoints

### Preferences

#### GET /api/profile/preferences

**Purpose:** Retrieve the user's coffee preferences and AI context.

**Authentication:** Required

**Response:**
```json
{
  "coffee": {
    "favoriteDrink": "Oat milk latte",
    "temperature": "iced",
    "milkPreference": "oat",
    "sweetness": "less",
    "strength": "medium",
    "caffeinePreference": "regular",
    "roastPreference": "medium",
    "brewMethod": "espresso",
    "dietaryPreference": ["Dairy-free"],
    "allergiesOrIntolerances": ""
  },
  "aiContext": {
    "customContext": "I prefer strong coffee and affordable recommendations.",
    "responseStyle": "balanced",
    "tone": "friendly",
    "recommendationStyle": "best",
    "usePreferencesInConversations": true
  }
}
```

**Error Cases:**
- 401: Unauthorized (invalid or missing token)
- 500: Internal server error

---

#### PUT /api/profile/preferences

**Purpose:** Update the user's coffee preferences and AI context.

**Authentication:** Required

**Request Body:**
```json
{
  "coffee": {
    "favoriteDrink": "Cold brew",
    "temperature": "iced"
  },
  "aiContext": {
    "responseStyle": "detailed"
  }
}
```

Both `coffee` and `aiContext` are optional. Only provided fields are updated (merge semantics).

**Response:**
```json
{
  "success": true,
  "coffee": { ... },
  "aiContext": { ... }
}
```

**Validation:**
- `temperature` must be one of: "hot", "iced", "either"
- `responseStyle` must be one of: "short", "balanced", "detailed"
- `tone` must be one of: "friendly", "casual", "professional", "playful"
- `recommendationStyle` must be one of: "best", "few", "explain"
- `dietaryPreference` must be an array of strings

**Error Cases:**
- 400: Invalid request body
- 401: Unauthorized
- 500: Internal server error

---

### Memories

#### GET /api/profile/memories

**Purpose:** Retrieve all memories for the authenticated user.

**Authentication:** Required

**Response:**
```json
{
  "memories": [
    {
      "id": "mem_abc123",
      "text": "You usually order iced lattes",
      "createdAt": "2026-09-08T10:00:00Z",
      "updatedAt": "2026-09-08T10:00:00Z"
    }
  ]
}
```

**Error Cases:**
- 401: Unauthorized
- 500: Internal server error

---

#### POST /api/profile/memories

**Purpose:** Create a new memory.

**Authentication:** Required

**Request Body:**
```json
{
  "text": "I prefer cold brew in the afternoon"
}
```

**Validation:**
- `text` is required, non-empty string
- Maximum length: 500 characters

**Response:**
```json
{
  "id": "mem_def456",
  "text": "I prefer cold brew in the afternoon",
  "createdAt": "2026-09-08T10:00:00Z",
  "updatedAt": "2026-09-08T10:00:00Z"
}
```

**Error Cases:**
- 400: Invalid request body
- 401: Unauthorized
- 500: Internal server error

---

#### PUT /api/profile/memories/{memory_id}

**Purpose:** Update an existing memory.

**Authentication:** Required

**Request Body:**
```json
{
  "text": "Updated memory text"
}
```

**Validation:**
- `text` is required, non-empty string
- Maximum length: 500 characters
- Memory must belong to the authenticated user

**Response:**
```json
{
  "id": "mem_abc123",
  "text": "Updated memory text",
  "createdAt": "2026-09-08T10:00:00Z",
  "updatedAt": "2026-09-08T11:00:00Z"
}
```

**Error Cases:**
- 400: Invalid request body
- 401: Unauthorized
- 404: Memory not found or not owned by user
- 500: Internal server error

---

#### DELETE /api/profile/memories/{memory_id}

**Purpose:** Delete a specific memory.

**Authentication:** Required

**Response:**
```json
{
  "success": true
}
```

**Error Cases:**
- 401: Unauthorized
- 404: Memory not found or not owned by user
- 500: Internal server error

---

#### DELETE /api/profile/memories

**Purpose:** Clear all memories for the authenticated user.

**Authentication:** Required

**Response:**
```json
{
  "success": true,
  "deletedCount": 5
}
```

**Error Cases:**
- 401: Unauthorized
- 500: Internal server error

---

## AI Context Endpoint

The backend should construct the AI context by combining:

1. **User preferences** from `users/{uid}/preferences/current`
   - Coffee preferences (for drink recommendations)
   - AI context (response style, tone, recommendations)

2. **Custom context** from the user's `aiContext.customContext`
   - This is freeform text the user has written

3. **Enabled memories** from `users/{uid}/memories`
   - Filter by `enabled` if the field exists
   - Include only recent/relevant memories if the list is long

4. **Conversation context** from the current conversation
   - Recent messages (last N messages or tokens)
   - Conversation summary if available

5. **Current user message**

The backend should format this context appropriately for the LLM provider without exposing the raw structure to the user.

### Context Structure (Internal)

```
[System prompt for coffee assistant]

[User's custom context]

[User's coffee preferences summary]

[Relevant memories]

[Conversation history]

[Current user message]
```

---

## Conversation History Preference

The `usePreferencesInConversations` toggle controls whether the AI uses the user's preferences in responses.

### When Enabled (default)

- Include coffee preferences in AI context
- Include custom context in AI context
- Include relevant memories in AI context

### When Disabled

- Exclude coffee preferences from AI context
- Exclude custom context from AI context
- Exclude memories from AI context
- The AI should still respond to direct questions about preferences

### Implementation Note

This is a frontend toggle that the backend should respect. The backend should check this flag before including preference data in the AI context.

---

## Delete Account

Account deletion requires Firebase Admin SDK on the backend.

### Recommended Flow

1. User initiates delete from the frontend.
2. Frontend calls `DELETE /api/profile/account`.
3. Backend verifies the user's identity via Firebase ID token.
4. Backend deletes all user data from Firestore:
   - `users/{uid}/profile/current`
   - `users/{uid}/preferences/current`
   - `users/{uid}/memories/{all}`
   - `users/{uid}/conversations/{all}`
   - `users/{uid}/orders/{all}`
   - `users/{uid}/summaries/{all}`
5. Backend deletes the Firebase Auth user.
6. Backend returns success.

### Security

- This operation is irreversible.
- The backend must verify the token before proceeding.
- Consider requiring re-authentication for this operation.

### Error Cases

- 401: Unauthorized
- 500: Failed to delete user data
- 500: Failed to delete Firebase Auth user

---

## Security

### Firebase ID Token Verification

- Use Firebase Admin SDK to verify tokens.
- Reject expired tokens.
- Reject tokens with invalid signatures.
- Extract UID from verified token payload.

### Firestore User Scoping

All user data must be scoped to `users/{authenticatedUid}/...`.

- Use the UID from the verified token, not from the request body.
- Never allow cross-user access.
- Enforce ownership at the Firestore rules level (already configured).

### Validation

- Validate all request bodies before processing.
- Sanitize string inputs.
- Enforce maximum lengths on text fields.
- Validate enum values against allowed options.

### CORS

Configure CORS to allow only the frontend origin.

```
Access-Control-Allow-Origin: https://grounded-coffeeshop-ai.web.app
Access-Control-Allow-Methods: GET, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
```

### Rate Limiting

Consider implementing rate limiting for:
- `PUT /api/profile/preferences`: 10 requests/minute
- `POST /api/profile/memories`: 20 requests/minute
- `DELETE /api/profile/memories`: 5 requests/minute

### Sensitive Logging

- Never log Firebase ID tokens.
- Never log API keys or secrets.
- Never log user passwords (not applicable here, but general rule).
- Log request IDs for debugging, not user content.

---

## Firestore Structure

```
users/
  {uid}/
    profile/
      current/
        email: string
        displayName: string
        photoURL: string
    preferences/
      current/
        coffee: CoffeePreferences
        aiContext: AIContext
    conversations/
      {convId}/
        title: string
        messages: Message[]
        createdAt: Timestamp
    memories/
      {memoryId}/
        text: string
        createdAt: Timestamp
        updatedAt: Timestamp
    orders/
      {orderId}/
        items: OrderItem[]
        total: number
        createdAt: Timestamp
    summaries/
      {summaryId}/
        summary: string
        createdAt: Timestamp
```

---

## Backend Dependencies

- Firebase Admin SDK (`firebase-admin`)
- FastAPI
- Pydantic (for request/response validation)
- Google Cloud Firestore (already configured)

---

## Environment Variables

```
FIREBASE_PROJECT_ID=grounded-coffeeshop-ai
FIREBASE_DATABASE=grounded
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

---

## Testing

### Unit Tests

- Test preference CRUD operations
- Test memory CRUD operations
- Test AI context construction
- Test input validation
- Test error handling

### Integration Tests

- Test full authentication flow
- Test Firestore operations with emulator
- Test cross-user isolation

### Security Tests

- Test unauthorized access
- Test cross-user data access attempts
- Test invalid token handling

---

## Implementation Priority

1. **Phase 1:** Authentication and basic preference CRUD
2. **Phase 2:** Memory CRUD
3. **Phase 3:** AI context construction
4. **Phase 4:** Account deletion
5. **Phase 5:** Rate limiting and advanced security
