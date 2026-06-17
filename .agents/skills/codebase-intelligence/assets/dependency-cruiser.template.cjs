/**
 * dependency-cruiser configuration template for a layered React/TypeScript frontend.
 *
 * Copy to your project root as .dependency-cruiser.cjs and adjust layer paths
 * to match your actual directory structure.
 *
 * Run: npx depcruise --config .dependency-cruiser.cjs --output-type json src/
 *
 * To generate an SVG dependency graph:
 *   npx depcruise --config .dependency-cruiser.cjs --output-type dot src/ | dot -T svg > deps.svg
 *
 * To initialize a fresh config interactively:
 *   npx depcruise --init
 *
 * Documentation: https://github.com/sverweij/dependency-cruiser
 *
 * @type {import('dependency-cruiser').IConfiguration}
 */
module.exports = {
  forbidden: [
    // ─── Always-on: circular imports ──────────────────────────────────────────
    {
      name: 'no-circular',
      severity: 'warn',
      comment:
        'Circular imports make the codebase brittle and harder to tree-shake. ' +
        'Resolve by extracting shared types into a separate module that both sides import.',
      from: {},
      to: { circular: true }
    },

    // ─── Always-on: orphaned files ─────────────────────────────────────────────
    {
      name: 'no-orphans',
      severity: 'info',
      comment:
        'Orphaned files (no other module imports them) may be dead code. ' +
        'Index files and type declaration files are excluded from this rule.',
      from: {
        orphan: true,
        pathNot: [
          '\\.d\\.ts$',
          '(^|/)index\\.(ts|tsx|js|jsx)$',
          '\\.test\\.(ts|tsx)$',
          '\\.spec\\.(ts|tsx)$',
          '\\.stories\\.(ts|tsx)$',
          'vite\\.config\\.',
          'vitest\\.config\\.'
        ]
      },
      to: {}
    },

    // ─── Layer rules: domain must not import UI ────────────────────────────────
    //
    // Adjust these path patterns to match your actual layer directories.
    //
    // Typical layered frontend structure:
    //   src/domain/       — business logic, models, pure functions
    //   src/services/     — API clients, external integrations
    //   src/store/        — state management (Zustand, Redux, Jotai, etc.)
    //   src/hooks/        — React hooks
    //   src/components/   — reusable UI components
    //   src/pages/        — route-level components
    //   src/ui/           — design system primitives
    //
    {
      name: 'no-ui-in-domain',
      severity: 'error',
      comment:
        'Domain logic must not import UI components or React hooks. ' +
        'Domain modules should be framework-agnostic and testable without a browser.',
      from: { path: '^src/domain' },
      to: { path: '^src/(components|pages|ui|hooks)' }
    },

    {
      name: 'no-react-in-services',
      severity: 'error',
      comment:
        'Service/API layer modules must not import React components or hooks. ' +
        'Services are infrastructure; they should be callable from tests without rendering.',
      from: { path: '^src/services' },
      to: { path: '^src/(components|pages|ui|hooks)' }
    },

    {
      name: 'no-page-in-component',
      severity: 'warn',
      comment:
        'Reusable components should not import page-level components — ' +
        'this creates tight coupling and prevents component reuse across routes.',
      from: { path: '^src/components' },
      to: { path: '^src/pages' }
    },

    // ─── Optional: no cross-feature imports ───────────────────────────────────
    //
    // Uncomment if you use a feature-based structure where features should be
    // independent of each other and communicate only through shared/ or api/.
    //
    // {
    //   name: 'no-cross-feature-imports',
    //   severity: 'warn',
    //   comment: 'Features should not import directly from other features.',
    //   from: { path: '^src/features/([^/]+)/' },
    //   to: {
    //     path: '^src/features/',
    //     pathNot: '^src/features/$1/'
    //   }
    // },

    // ─── No external package imports in domain ─────────────────────────────────
    //
    // Uncomment if you want to enforce that domain logic is pure TypeScript
    // with no third-party dependencies (useful for portability).
    //
    // {
    //   name: 'domain-no-external-deps',
    //   severity: 'warn',
    //   comment: 'Domain modules should not depend on third-party packages.',
    //   from: { path: '^src/domain' },
    //   to: { dependencyTypes: ['npm'] }
    // }
  ],

  options: {
    /* Which modules to NOT follow when encountered — keeps the graph manageable */
    doNotFollow: {
      path: 'node_modules'
    },

    /* Exclude these from the analysis entirely */
    exclude: {
      path: [
        '\\.test\\.(ts|tsx|js|jsx)$',
        '\\.spec\\.(ts|tsx|js|jsx)$',
        '\\.stories\\.(ts|tsx|js|jsx)$',
        '__generated__',
        '\\.d\\.ts$'
      ]
    },

    /* Follow TypeScript pre-compilation dependencies (before tsc transforms them) */
    tsPreCompilationDeps: true,

    /* Point to your tsconfig so path aliases and baseUrl resolve correctly */
    tsConfig: {
      fileName: 'tsconfig.json'
    },

    /* Optional: module systems to consider */
    moduleSystems: ['es6', 'cjs'],

    /* Visualization options (used when generating SVG/DOT graphs) */
    reporterOptions: {
      dot: {
        /* Collapse all node_modules into a single box */
        collapsePattern: 'node_modules/[^/]+'
      },
      archi: {
        /* Collapse top-level src/ subdirectories for a high-level overview */
        collapsePattern: '^src/[^/]+'
      },
      text: {
        highlightFocused: true
      }
    }
  }
};
