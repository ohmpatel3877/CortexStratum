// mem0 memory seeder - Run once to bootstrap the memory system
// Usage: node scripts/seed-memories.js

const MEMORIES = [
  // Architecture decisions
  { text: 'mem0 v0.2.1 plugin installed via MCP cloud endpoint at mcp.mem0.ai. Uses managed cloud tier with auto-scaling and SOC2 compliance.', type: 'architecture_decisions' },
  { text: 'Custom category system defined with 17 dev-specific categories to replace Mem0 defaults. Categories in .mem0.md.', type: 'architecture_decisions' },
  { text: 'Memory retention policy configured in .mem0.md: architecture_decisions and coding_conventions pinned forever, session_state pruned at 90 days.', type: 'architecture_decisions' },
  { text: 'Hybrid search strategy: semantic (0.7 weight) + BM25 keyword (0.3 weight) with cross-encoder reranking for optimal retrieval.', type: 'architecture_decisions' },
  { text: 'User identity: ohmpa. Projects are scoped by MEM0_APP_ID which equals the working directory name.', type: 'architecture_decisions' },
  { text: 'Active project: ai-memory-core. All memories stored under app_id derived from this project directory.', type: 'architecture_decisions' },

  // Coding conventions
  { text: 'Memories stored with infer=false and explicit metadata.type for deterministic categorization.', type: 'coding_conventions' },
  { text: 'Metadata always includes: type, confidence (0-1), source, and branch.', type: 'coding_conventions' },
  { text: 'Use /mem0-remember for explicit storage, not inline add_memory, unless automating in code.', type: 'coding_conventions' },
  { text: 'Run /mem0-dream --auto weekly to consolidate duplicates and prune stale entries.', type: 'coding_conventions' },
  { text: 'Store complete context: include file paths, function names, and module names in memory text.', type: 'coding_conventions' },

  // User preferences
  { text: 'User prefers dense, bullet-point output over prose. Markdown is forbidden in TUI output.', type: 'user_preferences' },
  { text: 'User wants autonomous operation: propose actions, dont just answer questions.', type: 'user_preferences' },
  { text: 'User values security: never commit secrets, always review auth/db changes, use verification gate.', type: 'user_preferences' },
  { text: 'User prefers local/self-hosted solutions where practical for data sovereignty.', type: 'user_preferences' },
  { text: 'User works on Windows with PowerShell 7+. All scripts should target this environment.', type: 'user_preferences' },

  // Anti-patterns
  { text: 'Dont run /mem0-dream in interactive mode during automation - use --auto flag instead.', type: 'anti_patterns' },
  { text: 'Dont mix project-level and global scopes accidentally. Explicit scope=global required for cross-project ops.', type: 'anti_patterns' },
  { text: 'Dont use add_memory without explicit type categorization - leads to orphan/untyped memories.', type: 'anti_patterns' },
  { text: 'Dont work from C:\\Windows\\System32 - MEM0_APP_ID becomes System32, polluting project scoping.', type: 'anti_patterns' },
];

async function main() {
  console.log('Seeding mem0 with', MEMORIES.length, 'base memories...\n');

  for (const mem of MEMORIES) {
    // Uses the mem0 API via fetch
    const response = await fetch('https://mcp.mem0.ai/mcp/add_memory', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${process.env.MEM0_API_KEY}`
      },
      body: JSON.stringify({
        text: mem.text,
        user_id: process.env.MEM0_USER_ID || 'ohmpa',
        app_id: process.env.MEM0_APP_ID || 'ai-memory-core',
        metadata: {
          type: mem.type,
          confidence: 0.95,
          source: 'seed_script',
          branch: 'main'
        },
        infer: false
      })
    });

    const result = await response.json();
    if (response.ok) {
      console.log(`  [OK] ${mem.type}: ${mem.text.substring(0, 60)}...`);
    } else {
      console.error(`  [FAIL] ${mem.type}: ${result.error || 'Unknown error'}`);
    }
  }

  console.log('\nSeed complete.');
}

main().catch(console.error);
