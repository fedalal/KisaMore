# Google Play reviewer access

KisaMore Battle has public spectator screens, but player controls require authentication.

## Recommended Play Console App access declaration

Select:
**All or some functionality is restricted**

Provide Google Play reviewers with a dedicated KisaMore test account.

Suggested account:
- Email: play-review@kisamore.farm
- Password: create a unique strong password and enter it only in Play Console.
- Do not commit the password to GitHub.

## Reviewer instructions

1. Launch KisaMore Battle.
2. Public battles can be viewed without signing in.
3. Open Profile or My Battle and sign in with the supplied reviewer account.
4. Use the supplied account to inspect player-only screens.
5. If there is no active battle assigned to the reviewer at review time, the reviewer can still
   access public spectator functionality. For a complete review, assign the test account to a
   non-production/demo battle with safe resource limits.

## Important

Before submitting for production review, ensure the reviewer account:
- is active;
- has no 2FA or email confirmation step blocking the reviewer;
- has access to at least one test battle if player controls need review;
- cannot trigger unsafe or expensive real-world operations.
