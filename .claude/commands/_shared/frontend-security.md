# Frontend Security Patterns

## Automated Security Scan

Run these greps on all new/modified `.tsx` and `.ts` files. Any match is a FAIL:

```bash
# Hardcoded API URLs (should use NEXT_PUBLIC_* env vars)
grep -rn "http://localhost:8123\|http://127.0.0.1:8123" cms/apps/web/src/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".next"

# Auth tokens in localStorage (must use httpOnly cookies)
grep -rn 'localStorage\.\(set\|get\)Item.*\(token\|auth\|session\|jwt\)' cms/apps/web/src/ --include="*.ts" --include="*.tsx"

# Unsanitized innerHTML (XSS vector)
grep -rn "dangerouslySetInnerHTML" cms/apps/web/src/ --include="*.tsx" | grep -v "DOMPurify"

# Hardcoded credentials
grep -rn "password.*=.*['\"]" cms/apps/web/src/ --include="*.ts" --include="*.tsx" | grep -v 'type\|interface\|placeholder\|label\|name='
```

## Security Checklist

Verify before marking any frontend step complete:

- [ ] All cookies set with `SameSite=Lax` (or `Strict` for auth cookies)
- [ ] Redirects preserve user's current locale (extract from pathname, validate against allowed list)
- [ ] No hardcoded credentials — use env vars for all secrets
- [ ] File uploads validate type AND size client-side before sending
- [ ] Auth tokens stored in httpOnly cookies only (never localStorage)
- [ ] No `dangerouslySetInnerHTML` without DOMPurify sanitization
- [ ] External links use `rel="noopener noreferrer"`
- [ ] User input displayed via React JSX (auto-escaped), never string interpolation
