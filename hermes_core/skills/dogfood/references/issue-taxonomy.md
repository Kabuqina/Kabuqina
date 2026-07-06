# Dogfood Issue Taxonomy

Use this taxonomy to classify findings consistently.

## Severity

### Critical

The issue blocks a primary user flow, causes data loss, exposes sensitive data,
or makes the product unusable for a major user group.

### High

The issue seriously impairs an important flow, creates a high-risk
misunderstanding, or prevents completion without a clear workaround.

### Medium

The issue causes confusion, visible friction, broken secondary behavior, or a
meaningful quality problem while a workaround exists.

### Low

The issue is cosmetic, minor, or unlikely to block progress, but still affects
polish, trust, or ease of use.

## Categories

### Functional

Broken behavior, incorrect state, failed navigation, failed form submission,
incorrect validation, missing data, or actions that do not do what they claim.

### Visual

Layout bugs, clipping, overlap, unreadable text, broken responsive behavior,
missing imagery, inconsistent spacing, or visual states that look unpolished.

### Accessibility

Keyboard traps, missing labels, poor focus order, insufficient contrast, screen
reader issues, inaccessible controls, or motion that cannot be controlled.

### Console

JavaScript errors, failed network requests, unhandled promise rejections, noisy
warnings, or errors that correlate with visible product behavior.

### UX

Confusing flow, unclear copy, missing feedback, surprising interaction,
unhelpful empty state, or excessive friction.

### Content

Broken links, stale copy, typos, inconsistent terminology, missing legal or
help text, or misleading claims.
