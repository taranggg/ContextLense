// Blocks `npm install` / `yarn` so the pnpm lockfile stays the single source of truth.
const agent = process.env.npm_config_user_agent || "";
if (!agent.startsWith("pnpm/")) {
  console.error("\nThis frontend uses pnpm. Install it with `corepack enable` (or `npm install -g pnpm`), then run `pnpm install`.\n");
  process.exit(1);
}
