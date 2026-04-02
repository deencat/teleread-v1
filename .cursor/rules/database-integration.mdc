---
description: Apply this rule when working with database operations, creating database queries, setting up database connections, or integrating authentication with database operations
globs: 
---
 # Database Integration Rules

## Core Principles
- Use Prisma as the ONLY database client
- NO direct database connections or alternative clients (e.g., Supabase client, raw SQL)
- All database operations MUST go through Prisma client
- Keep database logic in dedicated service layers
- Use the User Table "id" for referencing the user not the "clerkId"

## Database Access Pattern
```typescript
// ✅ CORRECT: Using Prisma client
import { prisma } from '@/lib/prisma'

async function getUserPosts(userId: string) {
  return await prisma.post.findMany({
    where: { userId },
    include: { author: true }
  })
}

// ❌ INCORRECT: Direct database connection
import { supabase } from '@/lib/supabase'
const { data } = await supabase.from('posts').select()
```

## Best Practices
1. Always use Prisma's type-safe queries
2. Implement database operations in service layers under `src/services/`
3. Use Prisma's middleware for cross-cutting concerns
4. Leverage Prisma's transaction API for atomic operations
5. Keep Prisma schema as source of truth
6. Use migrations for all schema changes

## Error Handling
```typescript
// Recommended error handling pattern
try {
  const result = await prisma.user.create({
    data: userData
  })
  return result
} catch (error) {
  if (error instanceof Prisma.PrismaClientKnownRequestError) {
    // Handle known Prisma errors (e.g., unique constraint violations)
  }
  throw error
}
```

## Service Layer Structure
```
src/
└── services/
    ├── user.service.ts
    ├── post.service.ts
    └── comment.service.ts
```

## Authentication Integration
- Use Clerk for auth, but store user data in database through Prisma
- Sync Clerk webhook events with database using Prisma operations
- Never bypass Prisma for user data management

## Performance Considerations
- Use Prisma's include/select for efficient queries
- Implement proper pagination using Prisma's skip/take
- Cache frequently accessed data at application level
- Use Prisma's findUnique for single record lookups

## Security Guidelines
- Never expose Prisma client on client-side
- Use server components or API routes for database operations
- Implement proper data validation before Prisma operations
- Use Prisma's middleware for audit logging if needed