# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type aware lint rules:

- Configure the top-level `parserOptions` property like this:

```js
   parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    project: ['./tsconfig.json', './tsconfig.node.json'],
    tsconfigRootDir: __dirname,
   },
```

- Replace `plugin:@typescript-eslint/recommended` to `plugin:@typescript-eslint/recommended-type-checked` or `plugin:@typescript-eslint/strict-type-checked`
- Optionally add `plugin:@typescript-eslint/stylistic-type-checked`
- Install [eslint-plugin-react](https://github.com/jsx-eslint/eslint-plugin-react) and add `plugin:react/recommended` & `plugin:react/jsx-runtime` to the `extends` list

## Testing

```bash
npm test             # run every test once (also: make test; make check runs lint + typecheck + test)
npm run test:watch   # rerun on save
```

Tests use [Vitest](https://vitest.dev) and sit next to the code they test:

- `*.test.ts` runs in Node, for logic: stores, parsers, formatters.
- `*.test.tsx` runs in jsdom with [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/), for components. Find elements by role and accessible name and act through `@testing-library/user-event`. `src/components/ui/FilterChips.dom.test.tsx` is the example.

Not every change needs tests. Test shared components, non-trivial logic and flows that would hurt to break.
