# ИИ-наблюдатель урока

Source: http://localhost:5173

To create a video from this capture, use the `website-to-hyperframes` skill.

## What's in This Capture

| File | Contents |
|------|----------|
| `screenshots/contact-sheet.jpg` | **View this first.** All scroll screenshots in labeled grid — see the entire page at a glance |
| `screenshots/scroll-*.png` | Individual viewport screenshots if you need detail on a specific section. |
| `extracted/tokens.json` | Design tokens: 19 colors, 2 fonts, 15 headings, 0 CTAs |
| `extracted/design-styles.json` | Computed styles from live DOM: typography hierarchy, button/card/nav styles, spacing scale, border-radius, box shadows. Primary data source for DESIGN.md. |
| `extracted/asset-descriptions.md` | One-line description of every downloaded asset. Read this for asset selection — only open individual files for safe-zone checking. |
| `extracted/visible-text.txt` | Page text in DOM order, prefixed with HTML tag (`[h1]`, `[p]`, `[a]`). Use as context — rephrase freely. |
| `assets/contact-sheet.jpg` | All downloaded images in one labeled grid. |
| `assets/` | Individual downloaded images, SVGs, and font files. |

## Brand Summary

- **Colors**: #14161C (surface-dark), #EEF1F6 (bg-light), #FFFFFF (bg-light), #6366F1 (accent), #06B6D4 (accent), #8B5CF6 (accent), #4F46E5 (accent), #3A3F4D (neutral), #F7F8FB (bg-light), #059669 (accent)
- **Fonts**: Manrope (400,500,600,700,800), Unbounded (500,600,700,800)
