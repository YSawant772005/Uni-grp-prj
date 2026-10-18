# University Shortlisting Tool — Project Rules

## 1. Follow Existing Documentation
1. Read the implementation plan, system architecture, UI flow, API contract, database schema, and project status document before coding.
2. Treat existing documents as the source of truth.
3. Do not rewrite, regenerate, or create additional planning documents unless absolutely necessary.
4. If requirements conflict, identify the issue and resolve it with the smallest sensible change.

## 2. Implementation and Code Quality
5. Implement actual working features instead of repeatedly producing plans or explanations.
6. Keep code as short, clean, readable, and maintainable as possible.
7. Do not write 10–15 lines when a clear, reliable one-line solution is sufficient.
8. Avoid overengineering, unnecessary abstractions, redundant files, excessive comments, duplicate code, and unnecessary dependencies.
9. Reuse suitable, reliable libraries instead of building existing functionality from scratch.
10. Follow the agreed technology stack and existing project architecture.
11. Preserve working code. Never delete or replace existing functionality without a valid reason.
12. Do not use hardcoded values or mock responses as substitutes for required production functionality.

## 3. Architecture and Technology
13. Use Vue 3, TypeScript, and Vite for the frontend.
14. Use Python and FastAPI for the backend.
15. Use PostgreSQL for persistent data storage.
16. Use Docker Compose for local multi-service development and NGINX for web serving/reverse proxying as defined in the architecture.
17. Keep frontend, backend, database, and configuration responsibilities separate and consistent with the specifications.
18. Use environment variables for configuration and provide an `.env.example` file without real credentials.

## 4. UI and User Experience
19. Follow the documented design, page layouts, routes, navigation, and user journeys.
20. Implement responsive, consistent interfaces using reusable components where appropriate.
21. Every interactive control must perform its intended action.
22. Provide proper loading, empty, error, retry, and success states.
23. Implement search, filters, sorting, pagination, and infinite scrolling wherever appropriate to the specifications.
24. Prevent duplicate results during pagination or infinite scrolling.
25. Keep navigation, filters, and relevant search state consistent when users move between pages.
26. Do not sacrifice usability or accessibility for shorter code.

## 5. Backend and API
27. Follow the documented API contract, endpoint names, request formats, response formats, and error conventions.
28. Validate incoming data and return clear, consistent errors.
29. Implement real database-backed operations for required features.
30. Add appropriate pagination, filtering, sorting, and limits to large queries.
31. Enforce authentication, authorization, and resource ownership on the server.
32. Avoid duplicate business logic and unnecessary API requests.
33. Add appropriate health checks and handle service failures gracefully.

## 6. Database and Data Integrity
34. Follow the agreed database schema and relationships.
35. Use migrations for schema changes instead of relying on manual database edits.
36. Add appropriate constraints, indexes, and transactions where needed.
37. Preserve existing user data and working records during changes.
38. Test migrations and database operations.
39. Clearly distinguish development seed data from verified real-world data.
40. Never fabricate university information, admission requirements, tuition fees, scholarships, visa rules, employment outcomes, or salary figures.
41. Preserve source links, supporting evidence, verification status, and timestamps wherever required.
42. Represent unknown or unverified information honestly rather than guessing.

## 7. Security and Reliability
43. Never commit passwords, API keys, tokens, or other secrets.
44. Validate and sanitize inputs appropriately.
45. Protect private user information and restrict access to authorized users.
46. Use secure authentication and session/token handling as specified.
47. Handle failures without silently losing data.
48. Do not run destructive commands, reset databases, or discard Git changes without permission.

## 8. Testing and Verification
49. Test every meaningful feature after implementation.
50. Run relevant backend tests, frontend tests, linting, type checks, database migrations, and production builds.
51. Test the actual integration between the frontend, backend, and database.
52. Test important edge cases, including invalid input, missing data, empty results, unauthorized access, and failed requests.
53. Fix errors before marking a task complete.
54. Never claim a feature works unless the relevant checks have actually passed.
55. Record existing failures separately from newly introduced failures.

## 9. Git and Version Control
56. Inspect the current branch and working-tree changes before editing.
57. Work in small, logical, reviewable phases.
58. Make focused commits after completing and verifying each meaningful phase.
59. Use clear commit messages, such as `feat: add university discovery` or `fix: resolve pagination issue`.
60. Never overwrite, discard, or commit unrelated user changes unintentionally.
61. Keep the repository clean and avoid committing build artifacts, temporary files, or secrets.

## 10. Project Status Tracking
62. Maintain `docs/UNIVERSITY_SHORTLISTING_PROJECT_STATUS.md` as the single source of implementation progress.
63. Use `[ ]` for not started, `[~]` for in progress, `[x]` for completed and verified, and `[!]` for blocked or failing.
64. After each meaningful task, record its status, test results, commit message/hash, and unresolved issues where applicable.
65. Mark a task complete only after implementation, relevant verification, and a focused commit.
66. Record what is not working and the exact next action needed to fix it.
67. Keep progress updates concise and factual.
68. Do not create new plans, reports, handbooks, or status documents when updating the existing status document is sufficient.

## 11. Working Method
69. Inspect the repository and understand existing code before making changes.
70. Implement one working phase at a time rather than changing the entire application in one enormous operation.
71. If a command fails, investigate the root cause instead of repeatedly running the same command.
72. Make reasonable implementation decisions when details are missing; ask questions only when a critical decision cannot safely be inferred.
73. Do not stop after describing the next steps. Continue with implementation, testing, and verification.
74. Do not claim completion based only on successful startup or a successful frontend build.
75. Prioritize a functioning, integrated, secure, and maintainable application over unnecessary complexity or excessive documentation.