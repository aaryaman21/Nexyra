# Nexyra AgriSense migration plan and audit

The existing app is Next.js 16.3.4 / React 19, Tailwind 4, Framer Motion,
Recharts, and FastAPI with SQLAlchemy (SQLite default, configurable database URL).
The ML dependencies include pandas, NumPy, scikit-learn, CatBoost and joblib.
Existing classifiers predict financial rule labels; household survey datasets
cannot train commodity price models. No agricultural history, weather archive,
news embeddings, collaborator implementation, or authentication layer was found.
Existing backend tests cover financial rules, justification and classification.

## Protected files
Keep app/globals.css, fonts and providers in app/layout.tsx, ThemeContext,
ThemeToggle, LaunchIntro, contextual loaders, all atmosphere/background/art and
FooterGarden components unchanged. Existing screenshots are in frontend/artifacts.
Capture current screenshots when a browser is available; historical screenshots
alone are not proof of current visual equivalence.

## Sequence
1. Preserve the financial page as a legacy route and all existing models/data/API.
2. Add validated agricultural data contracts and a separate artifact registry.
3. Build calendar-day targets, as-of features, chronological folds, A/B/C and
   naive comparisons, validation-only selection and isolated final testing.
4. Expose only successfully evaluated artifacts through agricultural API routes.
5. Repurpose the main dashboard content using the existing shell and classes.
6. Test leakage boundaries, fallback selection, registration and API failures;
   document source availability and unsupported features honestly.

## Release constraint
No agricultural winner can be registered from the datasets currently present.
Synthetic fixtures are only tests and must never populate the production registry.
Choose Maharashtra onion mandi/variety combinations only after coverage checks.
Live source access and historical availability must be verified independently.
