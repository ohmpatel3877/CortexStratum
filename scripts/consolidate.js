// DMN Consolidation Script
// Reads the agent-memory-mcp knowledge graph for behavioral rules and
// syncs them into skill-router.json triggers and limbic-blocklist.json inhibition rules.
// Usage: node scripts/consolidate.js

const { DatabaseSync } = require('node:sqlite');
const fs = require('fs');
const path = require('path');

const KNOWLEDGE_DB = path.resolve(process.env.USERPROFILE, 'github/agent-memory-mcp/.memory/metadata.db');
const SKILL_ROUTER = path.resolve(process.env.USERPROFILE, 'github/ai-memory-core/skills/skill-router.json');
const LIMBIC_BLOCKLIST = path.resolve(process.env.USERPROFILE, 'github/ai-memory-core/data/limbic-blocklist.json');
const IMPORTANCE_THRESHOLD = parseFloat(process.env.CONSOLIDATE_IMPORTANCE_THRESHOLD || '0.3');
const MAX_TRIGGER_TOKENS = parseInt(process.env.CONSOLIDATE_MAX_TRIGGER_TOKENS || '12', 10);

function parseTags(tagsJson) {
  try {
    const parsed = JSON.parse(tagsJson);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function tryParseContent(content) {
  try {
    return JSON.parse(content);
  } catch {
    return null;
  }
}

function tokenize(text) {
  return text.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

function buildTriggers(subject, content, tags) {
  const tokens = new Set(tokenize(subject));
  for (const t of tokenize(content)) tokens.add(t);
  for (const tag of tags) for (const t of tokenize(tag)) tokens.add(t);

  const triggerWords = Array.from(tokens).filter(t => t.length >= 2).slice(0, MAX_TRIGGER_TOKENS);
  if (triggerWords.length < 2) {
    triggerWords.push(subject.split(/\s+/)[0].toLowerCase().replace(/[^a-z0-9]/g, ''));
  }

  const skillName = 'behavioral-rule-' + subject.replace(/[^a-z0-9]+/gi, '-').toLowerCase().slice(0, 40);
  return { triggers: triggerWords, skills: [skillName], priority: 10 };
}

function readKnowledgeGraph() {
  if (!fs.existsSync(KNOWLEDGE_DB)) {
    console.warn(`[WARN] Knowledge graph not found at ${KNOWLEDGE_DB}`);
    return { reinforcement: [], inhibition: [] };
  }

  const db = new DatabaseSync(KNOWLEDGE_DB, { readOnly: true });
  const stmt = db.prepare(
    "SELECT rowid, subject, content, confidence, tags FROM profiles WHERE profile_type = 'behavioral_rule' AND confidence >= ?"
  );
  const rows = stmt.all(IMPORTANCE_THRESHOLD);

  db.close();

  const reinforcement = [];
  const inhibition = [];

  for (const row of rows) {
    const tags = parseTags(row.tags);
    const contentObj = tryParseContent(row.content) || {};
    const isReinforcement = tags.includes('reinforcement') || contentObj.reinforcement === true;
    const isInhibition = tags.includes('inhibition') || contentObj.inhibition === true;

    if (isReinforcement) {
      reinforcement.push({
        ...row,
        parsed_tags: tags,
        triggers: buildTriggers(row.subject, row.content, tags)
      });
    }
    if (isInhibition) {
      inhibition.push({
        ...row,
        parsed_tags: tags,
        inhibited_operation: contentObj.inhibited_operation || row.subject
      });
    }
  }

  return { reinforcement, inhibition };
}

function appendReinforcementToRouter(rules) {
  const router = JSON.parse(fs.readFileSync(SKILL_ROUTER, 'utf8'));
  let added = 0;

  for (const rule of rules) {
    const existing = router.rules.some(r =>
      r.triggers.some(t => rule.triggers.triggers.includes(t))
    );
    if (!existing) {
      router.rules.push(rule.triggers);
      added++;
    }
  }

  fs.writeFileSync(SKILL_ROUTER, JSON.stringify(router, null, 2) + '\n', 'utf8');
  return added;
}

function writeInhibitionBlocklist(rules) {
  const blocklist = {
    version: 1,
    description: 'Limbic-system inhibition rules — blocked or gated operations enforced by the verifier',
    generated_at: new Date().toISOString(),
    rules: rules.map(r => ({
      operation: r.inhibited_operation,
      subject: r.subject,
      confidence: r.confidence,
      reason: r.content,
      tags: r.parsed_tags,
      knowledge_graph_rowid: r.rowid
    }))
  };

  const dir = path.dirname(LIMBIC_BLOCKLIST);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(LIMBIC_BLOCKLIST, JSON.stringify(blocklist, null, 2) + '\n', 'utf8');
}

function main() {
  console.log('[consolidate] Reading knowledge graph...');
  const { reinforcement, inhibition } = readKnowledgeGraph();

  console.log(`[consolidate] Found ${reinforcement.length} reinforcement rules, ${inhibition.length} inhibition rules`);

  if (reinforcement.length > 0) {
    const added = appendReinforcementToRouter(reinforcement);
    console.log(`[consolidate] Appended ${added} new trigger entries to skill-router.json`);
  } else {
    console.log('[consolidate] No reinforcement rules to append');
  }

  if (inhibition.length > 0) {
    writeInhibitionBlocklist(inhibition);
    console.log(`[consolidate] Wrote ${inhibition.length} inhibition rules to limbic-blocklist.json`);
  } else if (!fs.existsSync(LIMBIC_BLOCKLIST)) {
    writeInhibitionBlocklist([]);
    console.log('[consolidate] Created empty limbic-blocklist.json');
  } else {
    console.log('[consolidate] limbic-blocklist.json already exists, no new inhibition rules');
  }

  console.log('[consolidate] DMN consolidation complete.');
  console.log('--- Summary ---');
  console.log(`  Knowledge graph: ${KNOWLEDGE_DB}`);
  console.log(`  Reinforcement rules processed: ${reinforcement.length}`);
  console.log(`  Inhibition rules processed: ${inhibition.length}`);
  console.log(`  Skill router: ${SKILL_ROUTER}`);
  console.log(`  Blocklist: ${LIMBIC_BLOCKLIST}`);
}

try {
  main();
} catch (err) {
  console.error('[consolidate] FATAL:', err.message);
  process.exit(1);
}
