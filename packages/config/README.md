# @gridkeep/config

Reserved for shared ESLint/TypeScript/Tailwind configuration once a second
frontend app or package needs to share it with `apps/web`. Not yet
populated: with a single frontend app, `apps/web` owns its own
`tsconfig.json` and `eslint.config.mjs` directly - extracting a shared
config now would be an abstraction with only one consumer.
