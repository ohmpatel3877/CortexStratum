#!/usr/bin/env python3
"""
Game Development Module — AI game development expert.
Specializes in Unity, Unreal Engine, and Roblox development.
Provides tools for game design analysis, project scaffolding,
mechanics design, monetization strategy, optimization, engine comparison,
and level design.

Registered as MCP tools via tools-mcp-server.py. Accessible via /gamedev command.

Architecture:
  Each function is a pure handler: dict in -> dict out.
  All game knowledge is embedded as constants (no external API calls).
  Stdlib only: json, os, re, math, textwrap, datetime, pathlib.
"""

import json
import textwrap
from typing import Any

# ---------------------------------------------------------------------------
# Embedded Knowledge Bases
# ---------------------------------------------------------------------------

GENRE_TAXONOMY = {
    "rpg": {
        "core_loop": "Explore -> Encounter enemies -> Earn XP/loot -> Upgrade -> Repeat",
        "target_audiences": ["core gamers", "fantasy fans", "narrative lovers"],
        "revenue_models": [
            "premium",
            "dlc_expansions",
            "cosmetic_microtransactions",
            "subscription",
        ],
        "avg_session": "30-120 min",
        "retention_drivers": [
            "character progression",
            "gear collection",
            "story cliffhangers",
            "social guilds",
        ],
    },
    "fps": {
        "core_loop": "Spawn -> Acquire weapons -> Eliminate opponents -> Score/rank -> Repeat",
        "target_audiences": ["competitive gamers", "action fans", "esports viewers"],
        "revenue_models": ["premium", "battle_pass", "cosmetic_shop", "season_pass"],
        "avg_session": "10-45 min",
        "retention_drivers": [
            "rank progression",
            "new weapons",
            "seasonal content",
            "competitive matchmaking",
        ],
    },
    "puzzle": {
        "core_loop": "Receive puzzle -> Attempt solution -> Succeed/fail -> New puzzle -> Repeat",
        "target_audiences": ["casual gamers", "brain training", "commuters"],
        "revenue_models": [
            "freemium",
            "ad_supported",
            "hint_purchases",
            "subscription",
        ],
        "avg_session": "3-15 min",
        "retention_drivers": [
            "daily challenges",
            "difficulty curve",
            "new puzzle types",
            "social leaderboards",
        ],
    },
    "platformer": {
        "core_loop": "Navigate level -> Overcome obstacles -> Collect items -> Reach goal -> Repeat",
        "target_audiences": ["retro gamers", "speedrunners", "casual players"],
        "revenue_models": ["premium", "level_packs", "cosmetics"],
        "avg_session": "5-30 min",
        "retention_drivers": [
            "new worlds",
            "collectibles",
            "speedrun leaderboards",
            "unlockable characters",
        ],
    },
    "sim": {
        "core_loop": "Manage resources -> Build/expand -> Encounter challenges -> Optimize -> Repeat",
        "target_audiences": ["management fans", "creative builders", "strategy lovers"],
        "revenue_models": [
            "premium",
            "expansion_packs",
            "creator_marketplace",
            "subscription",
        ],
        "avg_session": "20-120 min",
        "retention_drivers": [
            "creative freedom",
            "progression systems",
            "community content",
            "regular updates",
        ],
    },
    "strategy": {
        "core_loop": "Gather intel -> Plan moves -> Execute strategy -> Adapt to opponent -> Repeat",
        "target_audiences": ["thinkers", "competitive players", "history buffs"],
        "revenue_models": ["premium", "faction_packs", "battle_pass", "cosmetics"],
        "avg_session": "20-90 min",
        "retention_drivers": [
            "ranked ladder",
            "new factions/civs",
            "tournaments",
            "meta shifts",
        ],
    },
    "horror": {
        "core_loop": "Explore -> Encounter threat -> Survive/escape -> Breathe -> Repeat",
        "target_audiences": ["thrill seekers", "streamers", "horror fans"],
        "revenue_models": ["premium", "chapter_dlc", "cosmetics"],
        "avg_session": "15-60 min",
        "retention_drivers": [
            "story reveals",
            "new monsters",
            "community theories",
            "streamability",
        ],
    },
    "idle": {
        "core_loop": "Buy upgrade -> Generate resources -> Wait/scale -> Buy more -> Repeat",
        "target_audiences": ["ultra-casual", "second-screen", "mobile-first"],
        "revenue_models": [
            "ad_supported",
            "iap_boosts",
            "premium_unlock",
            "subscription",
        ],
        "avg_session": "1-5 min (multiple per day)",
        "retention_drivers": [
            "exponential numbers",
            "prestige systems",
            "daily bonuses",
            "offline progress",
        ],
    },
    "roguelike": {
        "core_loop": "Start run -> Explore procedural level -> Die -> Unlock meta-progression -> Start new run",
        "target_audiences": ["hardcore gamers", "variety seekers", "streamers"],
        "revenue_models": ["premium", "character_unlocks", "expansion_dlc"],
        "avg_session": "15-60 min per run",
        "retention_drivers": [
            "procedural variety",
            "meta-progression",
            "discovery",
            "runs are different every time",
        ],
    },
    "social": {
        "core_loop": "Socialize -> Customize avatar/space -> Participate in events -> Express identity -> Repeat",
        "target_audiences": ["teens", "social gamers", "creative communities"],
        "revenue_models": [
            "cosmetic_shop",
            "subscription",
            "creator_marketplace",
            "event_pass",
        ],
        "avg_session": "10-90 min",
        "retention_drivers": [
            "social connections",
            "self-expression",
            "live events",
            "user-generated content",
        ],
    },
}

ENGINE_FEATURES = {
    "unity": {
        "language": "C#",
        "render_pipelines": [
            "Built-in",
            "URP (Universal Render Pipeline)",
            "HDRP (High Definition)",
        ],
        "strengths": [
            "Large community",
            "Cross-platform (25+ platforms)",
            "Asset Store",
            "ECS/DOTS for performance",
            "Addressables for memory",
            "XR support",
        ],
        "weaknesses": [
            "Less visual fidelity out of box vs Unreal",
            "Rendering pipeline fragmentation",
            "Premium features behind subscriptions",
        ],
        "best_for": ["Mobile games", "2D games", "VR/AR", "Indie 3D", "Cross-platform"],
        "learning_curve": "moderate",
        "notable_games": [
            "Hollow Knight",
            "Cuphead",
            "Genshin Impact",
            "Among Us",
            "Monument Valley",
        ],
        "optimization_techniques": [
            "Occlusion culling",
            "LOD groups",
            "Object pooling",
            "Sprite atlas",
            "Addressables",
            "Burst compiler",
            "Job system",
            "GPU instancing",
            "Texture compression",
            "Static batching",
        ],
    },
    "unreal": {
        "language": "C++ with Blueprints visual scripting",
        "render_features": [
            "Nanite (virtualized geometry)",
            "Lumen (dynamic GI)",
            "Temporal Super Resolution",
            "MetaHuman",
        ],
        "strengths": [
            "Best-in-class graphics",
            "Blueprints for rapid prototyping",
            "Gameplay Ability System (GAS)",
            "World Partition for open worlds",
            "Free until $1M revenue",
        ],
        "weaknesses": [
            "Steep learning curve",
            "C++ complexity",
            "Heavy editor hardware requirements",
            "Large build sizes",
            "Overkill for simple games",
        ],
        "best_for": [
            "AAA 3D",
            "Open world",
            "High-fidelity graphics",
            "FPS/TPS",
            "Architectural visualization",
        ],
        "learning_curve": "steep",
        "notable_games": [
            "Fortnite",
            "Black Myth: Wukong",
            "Satisfactory",
            "Tekken 8",
            "Hellblade 2",
        ],
        "optimization_techniques": [
            "Nanite for geometry",
            "LODs with Simplygon",
            "Texture streaming",
            "Level streaming/World Partition",
            "Blueprint nativization",
            "Forward shading for VR",
            "Occlusion culling volumes",
            "Physics LOD",
            "Niagara GPU particles",
            "Asset Manager for async loading",
        ],
    },
    "roblox": {
        "language": "Luau (typed Lua)",
        "render_features": [
            "Future lighting",
            "ShadowMap",
            "SurfaceAppearance PBR",
            "StreamingEnabled",
        ],
        "strengths": [
            "Massive built-in audience (70M+ DAU)",
            "Zero distribution friction",
            "Built-in multiplayer",
            "Creator marketplace monetization",
            "Young developer-friendly",
            "Cloud-hosted servers",
        ],
        "weaknesses": [
            "Platform lock-in",
            "Revenue split (Roblox takes ~75%)",
            "Limited engine control",
            "Primarily younger audience",
            "Performance constraints on low-end devices",
        ],
        "best_for": [
            "Social experiences",
            "UGC games",
            "Kid-friendly content",
            "Rapid prototyping",
            "Community-driven games",
        ],
        "learning_curve": "easy",
        "notable_games": [
            "Adopt Me!",
            "Brookhaven",
            "Blox Fruits",
            "Jailbreak",
            "Doors",
        ],
        "optimization_techniques": [
            "StreamingEnabled",
            "Parallel Lua",
            "Asset streaming",
            "Occlusion culling",
            "LOD via StreamingDistance",
            "Reduce part count with MeshParts",
            "Atmosphere/lighting budget",
            "Network ownership for physics",
            "PreloadAsync for assets",
            "BulkMoveTo for groups",
        ],
    },
    "godot": {
        "language": "GDScript, C#, C++ (GDExtension)",
        "render_features": ["Forward+", "Mobile renderer", "Compatibility renderer"],
        "strengths": [
            "Free and open-source (MIT)",
            "Lightweight editor",
            "Dedicated 2D engine",
            "Node-based architecture",
            "No revenue share",
        ],
        "weaknesses": [
            "Smaller community",
            "Fewer AAA titles",
            "Limited console export (third-party)",
            "Asset library smaller than Unity/Unreal",
        ],
        "best_for": [
            "2D games",
            "Indie 3D",
            "Open-source projects",
            "Lightweight games",
        ],
        "learning_curve": "easy-moderate",
        "notable_games": [
            "Cassette Beasts",
            "Brotato",
            "Dome Keeper",
            "Sonic Colors: Ultimate",
        ],
        "optimization_techniques": [
            "MultiMeshInstance",
            "Occlusion culling (4.x)",
            "LOD via GeometryInstance3D",
            "Object pooling",
            "Texture atlases",
            "Threaded loading",
            "Viewport culling",
            "Batching with CanvasGroup (2D)",
            "NavigationServer for pathfinding",
        ],
    },
}

MONETIZATION_PATTERNS = {
    "premium": {
        "player_experience": "pay once, own forever",
        "best_for": ["single-player", "story-driven", "indie", "AAA"],
        "avg_price": {"mobile": 4.99, "pc_console": 29.99, "aaa": 69.99},
        "pros": [
            "No pay-to-win concerns",
            "Predictable revenue per sale",
            "Player goodwill",
        ],
        "cons": ["Hard to acquire users", "No ongoing revenue", "Piracy risk"],
        "examples": ["Hollow Knight", "God of War", "Baldur's Gate 3"],
    },
    "freemium": {
        "player_experience": "free to start, pay for extras",
        "best_for": ["mobile", "social", "casual"],
        "pros": ["Large user base", "Viral potential", "Ongoing revenue"],
        "cons": [
            "Only 2-5% convert to paying",
            "Can feel pay-to-win",
            "Requires careful balance",
        ],
        "conversion_rate": "2-5%",
        "arpu_estimate": "$0.05-$2.00/month per user",
        "examples": ["Candy Crush", "Clash of Clans", "Genshin Impact"],
    },
    "subscription": {
        "player_experience": "monthly access to content",
        "best_for": ["MMOs", "live-service", "cloud gaming", "creator platforms"],
        "typical_pricing": "$4.99-$14.99/month",
        "pros": [
            "Predictable recurring revenue",
            "Player investment = retention",
            "Can bundle content",
        ],
        "cons": [
            "Content treadmill",
            "Player fatigue",
            "Competing with other subscriptions",
        ],
        "retention_mechanisms": [
            "exclusive items",
            "monthly currency drops",
            "subscriber-only events",
            "discounts",
        ],
        "examples": [
            "World of Warcraft",
            "Roblox Premium",
            "Fortnite Crew",
            "Apple Arcade",
        ],
    },
    "battle_pass": {
        "player_experience": "earn rewards by playing",
        "best_for": ["multiplayer", "competitive", "live-service"],
        "typical_pricing": "$9.99-$14.99 per season",
        "pros": ["Drives engagement", "FOMO conversion", "Renews each season"],
        "cons": [
            "Feels like a job",
            "Players without pass feel left out",
            "Requires constant content",
        ],
        "season_length": "6-12 weeks",
        "examples": ["Fortnite", "Call of Duty", "Apex Legends", "Dota 2"],
    },
    "gacha": {
        "player_experience": "random draws for characters/items",
        "best_for": ["RPG", "mobile", "anime-style", "collectible games"],
        "pros": [
            "Extremely high ARPU from whales",
            "Engagement through collection",
            "Drama/excitement of pulls",
        ],
        "cons": [
            "Predatory if not careful",
            "Regulatory scrutiny",
            "Player burnout/bankruptcy risk",
        ],
        "pity_system": "guarantee after X pulls (typically 50-90)",
        "ethical_guidelines": [
            "publish rates",
            "include pity timers",
            "no children-targeted gacha",
            "spending limits",
        ],
        "examples": [
            "Genshin Impact",
            "Honkai: Star Rail",
            "Fate/Grand Order",
            "Raid: Shadow Legends",
        ],
    },
    "ad_supported": {
        "player_experience": "free with ads, pay to remove",
        "best_for": ["hyper-casual", "puzzle", "idle", "mobile-first"],
        "ad_formats": [
            "interstitial",
            "rewarded video",
            "banner",
            "native",
            "playable",
        ],
        "eCPM": {"tier1": "$8-15", "tier2": "$3-8", "tier3": "$0.50-$3"},
        "pros": [
            "No paywall reduces friction",
            "Rewarded ads feel fair",
            "Can combine with IAP",
        ],
        "cons": ["Breaks immersion", "Lower per-user revenue", "Ad network dependency"],
        "examples": ["Subway Surfers", "Crossy Road", "Flappy Bird"],
    },
    "cosmetics_only": {
        "player_experience": "pay for style, not power",
        "best_for": ["competitive multiplayer", "esports", "social"],
        "pros": ["No pay-to-win accusations", "Player trust", "Esports viable"],
        "cons": [
            "Requires strong cosmetic desire",
            "Lower conversion than power purchases",
            "Needs great art team",
        ],
        "examples": ["Counter-Strike", "Dota 2", "Fortnite", "League of Legends"],
    },
    "creator_marketplace": {
        "player_experience": "players sell UGC to other players",
        "best_for": ["sandbox", "social", "UGC platforms"],
        "revenue_split": "platform takes 25-75%, creator gets remainder",
        "pros": [
            "Infinite content supply",
            "Community investment",
            "Creators market the game",
        ],
        "cons": ["Moderation headaches", "IP infringement risk", "Quality variance"],
        "examples": [
            "Roblox",
            "Fortnite Creative",
            "Minecraft Marketplace",
            "The Sandbox",
        ],
    },
}

GAME_DESIGN_PRINCIPLES = {
    "flow_theory": "Optimal experience when challenge matches skill — too hard = anxiety, too easy = boredom. Vary difficulty dynamically.",
    "skinner_box": "Variable-ratio reward schedules (random drops, crits, loot boxes) are the most addictive. Use ethically.",
    "intrinsic_vs_extrinsic": "Intrinsic rewards (mastery, discovery, autonomy) sustain long-term play better than extrinsic (points, badges, currency).",
    "ikea_effect": "Players value things more when they helped create them (character customization, base building, item crafting).",
    "loss_aversion": "Players feel losses 2x more intensely than equivalent gains. 'Lose your streak' motivates more than 'gain a bonus'.",
    "variable_ratio": "Random rewards on random intervals (like slot machines) create the strongest habit loop. Use with care.",
    "social_proof": "Showing what friends are doing (X is online, Y just unlocked Z) drives engagement via herd behavior.",
    "fomo": "Limited-time events, seasonal items, daily streaks — fear of missing out is a powerful retention tool.",
    "autonomy": "Meaningful choices matter. If every 'choice' leads to the same outcome, players feel manipulated.",
    "competence": "Players need to feel they're getting better. Clear feedback loops (score, rank, unlocks) validate growth.",
    "relatedness": "Social connection: guilds, co-op, competition, chat, and shared experiences build lasting communities.",
    "juice": "Exaggerated feedback (screen shake, particles, sound, slowdown on hit) makes actions feel satisfying beyond their mechanical effect.",
    "emergent_gameplay": "Simple rules that create complex, unexpected scenarios (Breath of the Wild physics, immersive sims like Dishonored).",
    "risk_vs_reward": "Players should constantly weigh 'do I push deeper for more loot, or extract now?' — this tension creates memorable moments.",
    "progression_illusion": "Early levels should fly by (fast dopamine). Exponential XP curves keep the treadmill going without making it obvious.",
}

ENGINE_OPTIMIZATION = {
    "unity": {
        "low_fps": {
            "diagnosis": "Frame rate drops below target (30/60 FPS). Common causes: too many draw calls, heavy scripts in Update(), unbatched UI, complex shaders.",
            "solutions": [
                {
                    "technique": "Enable GPU instancing for repeated meshes",
                    "impact": "high",
                    "implementation": "Check 'Enable GPU Instancing' on materials. For SRP Batcher compatibility, use same shader variant across materials.",
                },
                {
                    "technique": "Use object pooling instead of Instantiate/Destroy",
                    "impact": "high",
                    "implementation": "Pre-instantiate a pool of objects at scene load. Enable/disable instead of creating/destroying. Use Queue<T> for the pool.",
                },
                {
                    "technique": "Move heavy logic from Update() to coroutines or Jobs",
                    "impact": "high",
                    "implementation": "Use C# Jobs/Burst for data processing. InvokeRepeating with longer intervals for non-critical updates.",
                },
                {
                    "technique": "Profile with Unity Profiler to find bottlenecks",
                    "impact": "high",
                    "implementation": "Window > Analysis > Profiler. Deep profile to see per-method costs. Focus on GC.Alloc spikes.",
                },
                {
                    "technique": "Combine static meshes with StaticBatchingUtility",
                    "impact": "medium",
                    "implementation": "Mark GameObjects as Static. Unity batches them at build time. Cuts draw calls by 80%+ for static geometry.",
                },
            ],
            "profiling_tools": [
                "Unity Profiler",
                "Frame Debugger",
                "Memory Profiler",
                "Rendering Debugger",
            ],
            "common_pitfalls": [
                "Camera.main in Update() (does FindGameObjectWithTag internally)",
                "String concatenation in hot paths (use StringBuilder)",
                "GetComponent in Update() (cache in Awake/Start)",
                "Instantiating many objects at once (spread across frames)",
            ],
        },
        "draw_calls": {
            "diagnosis": "Too many draw calls per frame. CPU-bound rendering. Mobile target: <100 draw calls. PC target: <2000 draw calls.",
            "solutions": [
                {
                    "technique": "Use the SRP Batcher (URP/HDRP)",
                    "impact": "high",
                    "implementation": "SRP Batcher batches by shader variant, not by material. Keep shader variants consistent. Enabled by default in URP/HDRP.",
                },
                {
                    "technique": "Combine meshes with Mesh.CombineMeshes or tools like MeshBaker",
                    "impact": "high",
                    "implementation": "Use Mesh.CombineMeshes() for static geometry at runtime or build time. Reduces thousands of objects to dozens.",
                },
                {
                    "technique": "Use Sprite Atlas for 2D",
                    "impact": "high",
                    "implementation": "Create > 2D > Sprite Atlas. Add all sprites for a scene. Set packing tight. Check 'Include in Build'. Enable 'Use Sprite Atlas' in project settings.",
                },
                {
                    "technique": "Reduce material count via texture atlasing",
                    "impact": "medium",
                    "implementation": "Combine textures into atlas sheets. Each unique material = one draw call. Aim for <100 materials visible per frame.",
                },
                {
                    "technique": "Use LOD groups to reduce detail at distance",
                    "impact": "medium",
                    "implementation": "Add LOD Group component. Create 3 LOD levels (100%, 50%, 10% triangle count). Transition at appropriate screen percentages.",
                },
            ],
            "profiling_tools": [
                "Frame Debugger",
                "Rendering Debugger (URP)",
                "Scene view: Stats overlay",
            ],
            "common_pitfalls": [
                "Too many Point Lights (each adds draw calls)",
                "Transparent objects don't batch well",
                "UI Canvases dirty every frame (separate dynamic/static canvases)",
                "Post-processing stack too deep",
            ],
        },
        "memory": {
            "diagnosis": "High memory usage causing GC spikes, app termination on mobile, or editor slowdowns.",
            "solutions": [
                {
                    "technique": "Use Addressables for asset management",
                    "impact": "high",
                    "implementation": "Convert assets to Addressables. Load/Unload via Addressables.LoadAssetAsync. Release when done. Reduces persistent memory dramatically.",
                },
                {
                    "technique": "Implement texture compression and mipmaps",
                    "impact": "high",
                    "implementation": "Set texture import settings: Max Size appropriate, Compression to ASTC (mobile) or BC7 (PC). Enable Generate Mip Maps only when needed.",
                },
                {
                    "technique": "Use asset bundles or Addressables for DLC",
                    "impact": "high",
                    "implementation": "Group content by feature/level. Download on demand. Unload unused assets with Resources.UnloadUnusedAssets().",
                },
                {
                    "technique": "Profile with Memory Profiler package",
                    "impact": "medium",
                    "implementation": "Package Manager > Memory Profiler. Take snapshots. Compare before/after scene transitions. Look for leaked textures and meshes.",
                },
            ],
            "profiling_tools": [
                "Memory Profiler",
                "Profiler (Memory module)",
                "Addressables Analyzer",
            ],
            "common_pitfalls": [
                "Resources folder loads everything at startup",
                "Audio clips decompress fully in memory (use streaming for music)",
                "Font textures for CJK can be 16MB+ each",
                "Empty GameObjects with Colliders (they still eat memory)",
            ],
        },
        "load_times": {
            "diagnosis": "Long loading screens. Players drop off if load >10 seconds on mobile, >5 seconds on PC.",
            "solutions": [
                {
                    "technique": "Use async scene loading with LoadSceneAsync",
                    "impact": "high",
                    "implementation": "SceneManager.LoadSceneAsync with allowSceneActivation = false. Show loading screen during load. Activate when allowSceneActivation = true.",
                },
                {
                    "technique": "Preload critical assets in a bootstrap scene",
                    "impact": "high",
                    "implementation": "Lightweight 'Loading' scene that preloads UI, player character, and common materials before transitioning to main menu.",
                },
                {
                    "technique": "Stream world in chunks (World Streaming / SECTR)",
                    "impact": "high",
                    "implementation": "Divide large worlds into scenes. Load/unload scenes additively around player. Unity's Multi-Scene editing supports this.",
                },
                {
                    "technique": "Strip unused shader variants",
                    "impact": "medium",
                    "implementation": "Project Settings > Graphics > Shader Stripping. Configure which variants to strip. Can reduce build size and load time significantly.",
                },
            ],
            "profiling_tools": [
                "Profiler (Loading section)",
                "Build Report tool",
                "Asset Import times in Editor log",
            ],
            "common_pitfalls": [
                "Awake() doing heavy work (use Start() or coroutine)",
                "Resources.LoadAll in Awake (blocks main thread)",
                "Large serialized fields in MonoBehaviour (serialize with [SerializeReference] carefully)",
                "Audio import decompresses on load (change to streaming for long clips)",
            ],
        },
    },
    "unreal": {
        "low_fps": {
            "diagnosis": "Blueprint or C++ bottlenecks, GPU overdraw, too many actors ticking, or Nanite/Lumen overhead.",
            "solutions": [
                {
                    "technique": "Nativize performance-critical Blueprints to C++",
                    "impact": "high",
                    "implementation": "Blueprint Nativization in Project Settings > Packaging. Or manually convert hot Blueprints to C++ actors.",
                },
                {
                    "technique": "Reduce tick frequency or disable tick on idle actors",
                    "impact": "high",
                    "implementation": "Set Actor Tick Interval to 0.05-0.1s for non-critical actors. Disable tick on actors >200m from camera. Use Timer instead of Tick where possible.",
                },
                {
                    "technique": "Profile with Unreal Insights",
                    "impact": "high",
                    "implementation": "Unreal Insights > Start Trace. Record session. Analyze frame timing, game thread, render thread, GPU.",
                },
                {
                    "technique": "Use GPU Scene for instance culling",
                    "impact": "medium",
                    "implementation": "Enable 'Support GPU Scene' in project settings. Automatically culls instances on GPU. Works with ISM/HISM components.",
                },
                {
                    "technique": "Optimize Niagara particle systems",
                    "impact": "medium",
                    "implementation": "Set fixed bounds for particles. Use GPU simulation for >1000 particles. Kill particles outside camera view. Limit overdraw with sprite alignment.",
                },
            ],
            "profiling_tools": [
                "Unreal Insights",
                "stat unit / stat fps",
                "stat scenerendering",
                "GPU Visualizer (Ctrl+Shift+,)",
                "RenderDoc",
            ],
            "common_pitfalls": [
                "Tick enabled on all actors by default",
                "Casting in Tick (cache references)",
                "Line traces every frame (use timers or events)",
                "Blueprint nodes running on construction script for every instance",
                "Mesh collision complexity set too high",
            ],
        },
        "draw_calls": {
            "diagnosis": "High draw call count causing CPU render thread bottleneck. Massively impacts console and lower-end hardware.",
            "solutions": [
                {
                    "technique": "Use Instanced Static Meshes (ISM/HISM)",
                    "impact": "high",
                    "implementation": "Replace StaticMeshActors with InstancedStaticMeshComponent for repeated meshes (foliage, rocks, props). HISM for LOD support. ISM for single LOD.",
                },
                {
                    "technique": "Enable Nanite for high-poly static meshes",
                    "impact": "high",
                    "implementation": "Enable Nanite on static mesh assets. Automatically handles LOD, culling, and draw calls. Only for opaque, non-deformable meshes.",
                },
                {
                    "technique": "Merge static meshes in level design",
                    "impact": "medium",
                    "implementation": "Select meshes > Merge Actors tool. Creates single merged mesh. Great for background geometry. Include LODs in merge.",
                },
                {
                    "technique": "Use Material Instances instead of unique materials",
                    "impact": "medium",
                    "implementation": "Create Master Material. Make Material Instances for variations. Same master = same draw batch = fewer draw calls.",
                },
            ],
            "profiling_tools": [
                "stat RHI",
                "stat scenerendering",
                "GPU Visualizer",
                "RenderDoc frame capture",
            ],
            "common_pitfalls": [
                "Translucent materials break all batching",
                "Dynamic material instances create new materials per instance",
                "Landscape components add draw calls per component (adjust component size)",
                "Skeletal mesh per-character is expensive (consider mesh merging for crowds)",
            ],
        },
        "memory": {
            "diagnosis": "Out of video memory on GPU, or high RAM usage causing console/page to disk lag.",
            "solutions": [
                {
                    "technique": "Use texture streaming pool with budget",
                    "impact": "high",
                    "implementation": "r.Streaming.PoolSize in console. Set based on target hardware. Use texture LOD bias to reduce resolution at distance. Enable 'Streaming' on textures.",
                },
                {
                    "technique": "Implement level streaming with World Partition",
                    "impact": "high",
                    "implementation": "Enable World Partition for large worlds. Cells load/unload based on distance. Set streaming distance per Data Layer.",
                },
                {
                    "technique": "Use Asset Manager for async loading",
                    "impact": "high",
                    "implementation": "Asset Manager + Primary Asset Labels. Load bundles asynchronously. Unload when no longer needed. FSoftObjectPath for lazy references.",
                },
                {
                    "technique": "Compress audio with ADPCM for SFX, stream music",
                    "impact": "medium",
                    "implementation": "Set Sound Wave compression: ADPCM for short SFX, Ogg Vorbis streaming for long music/ambient. Set quality per target platform.",
                },
            ],
            "profiling_tools": [
                "stat memory",
                "MemReport -full",
                "Session Frontend > Memory Profiler",
                "Unreal Insights > Memory trace",
            ],
            "common_pitfalls": [
                "Hard references in Blueprint prevent garbage collection",
                "Loading entire world instead of cells",
                "UI textures at 4K (scale down to actual display size)",
                "Keeping all level variants in memory (use Data Layers)",
            ],
        },
        "build_size": {
            "diagnosis": "Final packaged build exceeds target platforms limits: iOS 4GB, Switch 32GB, etc.",
            "solutions": [
                {
                    "technique": "Use chunking/Pak files for downloadable content",
                    "impact": "high",
                    "implementation": "Primary Asset Labels > Chunk ID. Separate base build from downloadable chunks. Players download only what they need.",
                },
                {
                    "technique": "Compress textures with platform-appropriate format",
                    "impact": "high",
                    "implementation": "TC_DXT5 for PC, TC_ASTC for mobile, TC_BC7 for high quality. Set texture group LOD bias per platform.",
                },
                {
                    "technique": "Strip unused plugins and engine modules",
                    "impact": "high",
                    "implementation": "Disable plugins not needed. Edit .uproject to remove module dependencies. Custom Engine build strips sections you never use.",
                },
                {
                    "technique": "Enable Share Material Shader Code in project settings",
                    "impact": "medium",
                    "implementation": "Project Settings > Packaging > Share Material Shader Code = true. Reduces shader library size significantly.",
                },
                {
                    "technique": "Remove editor-only content from cooked build",
                    "impact": "medium",
                    "implementation": "Use 'Editor Only' Data Layer. Exclude from cook. Remove debug meshes, editor helpers, documentation textures.",
                },
            ],
            "profiling_tools": [
                "Build > Build and Submission > Package Project",
                "Unreal Insights > File I/O",
                "Pak Explorer tool",
            ],
            "common_pitfalls": [
                "Starter Content packs left in build",
                "4K textures for small props",
                "All audio uncompressed",
                "Entire engine compiled into build (use modular features)",
                "Shaders for every quality level included",
            ],
        },
    },
    "roblox": {
        "low_fps": {
            "diagnosis": "Client FPS drops below 30. Often CPU-bound from too many parts, scripts, or physics objects.",
            "solutions": [
                {
                    "technique": "Use StreamingEnabled to load only nearby content",
                    "impact": "high",
                    "implementation": "Workspace > StreamingEnabled = true. Set StreamingTargetRadius. Content beyond radius is unloaded. Combine with StreamingDistance on models.",
                },
                {
                    "technique": "Reduce part count with MeshParts and Unions",
                    "impact": "high",
                    "implementation": "Replace complex builds of 100+ parts with a single MeshPart. Use CSG unions for static geometry. Each Part costs CPU.",
                },
                {
                    "technique": "Use Parallel Lua for compute-heavy logic",
                    "impact": "high",
                    "implementation": "Actor:StartParallel(script). Parallel scripts run on separate threads. Use SharedTable for communication. Not all APIs are parallel-safe.",
                },
                {
                    "technique": "Move logic to server, keep client lean",
                    "impact": "high",
                    "implementation": "Server handles: physics, AI, data validation, rewards. Client handles: input, UI, effects, local prediction. RemoteEvents bridge them.",
                },
                {
                    "technique": "Limit Workspace gravity/terrain detail",
                    "impact": "medium",
                    "implementation": "Set Workspace.Gravity lower if not needed. Use simpler terrain material textures. Set Terrain decoration to minimal in non-critical areas.",
                },
            ],
            "profiling_tools": [
                "Developer Console (F9) > MicroProfiler",
                "Script Performance tab",
                "Client > Rendering stats",
                "Developer Stats bar",
            ],
            "common_pitfalls": [
                "While true loops without wait() or task.wait()",
                "Touched event on every part in a large model",
                "Heartbeat connection without throttle",
                "Adding/removing parts in a loop (batch with BulkMoveTo)",
                "Heavy UI updates every frame",
            ],
        },
        "network_lag": {
            "diagnosis": "Players experiencing rubber-banding, delayed actions, or desync with other players.",
            "solutions": [
                {
                    "technique": "Set Network Ownership correctly",
                    "impact": "high",
                    "implementation": "Assign network ownership of parts to the player interacting with them. Use Part:SetNetworkOwner(player). Server-authoritative for critical actions.",
                },
                {
                    "technique": "Use RemoteEvents sparingly, batch updates",
                    "impact": "high",
                    "implementation": "Batch multiple property changes into a single RemoteEvent fire. Fire at most 20Hz for positional updates. Use UnreliableRemoteEvent if loss is acceptable.",
                },
                {
                    "technique": "Implement client-side prediction",
                    "impact": "high",
                    "implementation": "Client moves immediately, sends to server. Server validates and corrects if needed. Smooth correction with lerp to avoid snapping.",
                },
                {
                    "technique": "Reduce replication distance for non-critical objects",
                    "impact": "medium",
                    "implementation": "Set Model/Part replication distance. Only replicate what the player can see or interact with. Use StreamingDistance.",
                },
                {
                    "technique": "Profile network with Developer Console",
                    "impact": "medium",
                    "implementation": "F9 > Network tab. Monitor send/receive rates, ping, packet loss. Aim for <20KB/s per client.",
                },
            ],
            "profiling_tools": [
                "Developer Console > Network tab",
                "Script > Network Ownership view",
                "Replication stats",
            ],
            "common_pitfalls": [
                "Replicating every minor property change",
                "Physics parts with CanCollide on server but not client-relevant",
                "Large RemoteEvent payloads (keep <1KB)",
                "Not using throttle for high-frequency events (RunService.Heartbeat:Wait() minimum)",
            ],
        },
    },
    "godot": {
        "low_fps": {
            "diagnosis": "Low frame rates, often from excessive nodes, heavy _process, or unoptimized rendering.",
            "solutions": [
                {
                    "technique": "Use MultiMeshInstance for repeated meshes",
                    "impact": "high",
                    "implementation": "MultiMeshInstance3D with MultiMesh resource. Add instances via set_instance_transform(). Each instance = 1 draw call instead of 1 per mesh.",
                },
                {
                    "technique": "Move expensive _process to _physics_process or timers",
                    "impact": "high",
                    "implementation": "_process runs every frame. _physics_process runs at fixed 60Hz. SceneTreeTimer or Timer node for anything slower than every 100ms.",
                },
                {
                    "technique": "Enable occlusion culling (Godot 4.x)",
                    "impact": "high",
                    "implementation": "Project Settings > Rendering > Occlusion Culling > Use Occlusion Culling = true. Bake occlusion data. Objects behind walls get culled.",
                },
                {
                    "technique": "Use object pooling for frequently created/destroyed objects",
                    "impact": "high",
                    "implementation": "Pre-create nodes in a pool group. call_deferred('add_child') and queue_free() are main-thread expensive. Pool avoids both.",
                },
                {
                    "technique": "Reduce transparency and particle overdraw",
                    "impact": "medium",
                    "implementation": "Transparent materials render in separate pass. Limit transparency to essential VFX. GPU particles for high counts. Limit particle lifetime.",
                },
            ],
            "profiling_tools": [
                "Debugger > Profiler (bottom panel)",
                "Debugger > Monitors",
                "Rendering > View Information (editor)",
                "Rendering > Frame Time Graph",
            ],
            "common_pitfalls": [
                "get_node() in _process (cache in @onready var)",
                "Many Area2D/3D with monitoring (use groups + signals instead)",
                "TextEdit/RichTextLabel updating every frame",
                "Physics layers unconfigured (all objects collide with all)",
            ],
        },
    },
}

GAME_LEVEL_DESIGN = {
    "tutorial": {
        "principles": [
            "Teach one mechanic at a time. Never overwhelm.",
            "Make success unavoidable on first attempt (the player can't fail learning jump).",
            "Use visual language: yellow ledges = climbable, red = danger. Establish early, respect always.",
            "After teaching, immediately test. Teach jump, then require jump.",
            "Let players discover depth on their own. Show the door, don't push them through.",
            "Keep tutorials skippable for experienced players.",
            "Text should be ambient (signs, NPC dialogue) — not popup boxes that pause gameplay.",
        ],
        "flow_diagram": "Intro -> Teach Mechanic A (safe) -> Test Mechanic A -> Teach Mechanic B -> Test A+B -> Boss Test (all mechanics) -> World opens",
        "pacing_guide": "1-3 minutes per mechanic. Total tutorial <15 minutes. Every 90 seconds, something new happens (enemy, environment change, story beat).",
        "landmark_system": "Use unique visual landmarks at decision points. 'Turn right at the glowing crystal' is better than 'go to coordinates.'",
        "encounter_design": [
            "Safe practice zone (enemies don't attack, just walk)",
            "Single enemy (teaches combat)",
            "Two enemies (teaches targeting)",
            "Enemy + obstacle (teaches combat + movement)",
            "Mini-boss with pattern (tests all learned mechanics)",
        ],
        "playtesting_checklist": [
            "Did playtesters understand mechanics without reading?",
            "Did anyone get stuck for >30 seconds?",
            "Did anyone try to skip and miss critical knowledge?",
            "Would a 6-year-old or non-gamer complete the tutorial?",
            "Can you complete tutorial in <10 minutes?",
        ],
    },
    "boss_fight": {
        "principles": [
            "Three phases: introduction (show attacks), escalation (faster/more), desperation (new pattern, high risk).",
            "Clear telegraphs. Every attack must be readable 0.5-1s before it hits.",
            "Safe windows. After every attack combo, player gets 2-3s to counter-attack.",
            "Arena matters. Changing arena (rising lava, crumbling platforms) adds tension.",
            "Music cues. Phase transitions should be audible before visible.",
            "Fair difficulty. If you can't beat your own boss without taking damage, it's unfair.",
            "Death should teach. Each death should reveal something about the pattern.",
        ],
        "flow_diagram": "Approach -> Phase 1 (learn pattern) -> Phase 2 (pattern accelerates) -> Phase 3 (new attacks) -> Victory (reward + spectacle)",
        "pacing_guide": "3-7 minutes per phase. Boss fight total 8-20 minutes. No phase should outstay its welcome.",
        "landmark_system": "Arena landmarks: cover positions, environmental hazards, power-up spawns. Telegraph danger zones with colored indicators.",
        "encounter_design": [
            "Phase 1: 2 attack types, slow telegraphed, large safe windows",
            "Phase 2: 3-4 attack types, 30% faster, environment changes (floor breaks)",
            "Phase 3: New ultimate attack, no safe zone camping, arena shrinks or shifts",
            "Adds (minions) in phase 2-3 to split attention, but they should die in 1-2 hits",
        ],
        "playtesting_checklist": [
            "Can players read every attack before it hits?",
            "Are there safe positions that trivialize the fight?",
            "Do phases feel distinct mechanically (not just more HP)?",
            "Is the victory moment satisfying (slow-mo, camera shake, loot explosion)?",
            "Did any tester quit in frustration?",
        ],
    },
    "exploration": {
        "principles": [
            "Weenies: place visible, interesting landmarks to draw players. See Disney's concept.",
            "Breadcrumbs: trails of collectibles, lights, or enemies leading toward points of interest.",
            "Loop back: connect areas so players return to familiar ground from a new angle.",
            "Secrets density: 1 hidden thing per 2-3 minutes of exploration space.",
            "Negative space: empty areas make discoveries feel more special. Don't pack every corner.",
            "Verticality: multiple elevation levels multiply exploration space and combat options.",
            "Navigation aids: maps that reveal as you go, compass markers for discovered landmarks.",
        ],
        "flow_diagram": "Safe Hub -> Path A (visible goal) -> Side path (optional secret) -> Path B -> Discovery (landmark) -> Loop back to hub -> New area unlocked",
        "pacing_guide": "Discover something every 30-90 seconds: item, vista, enemy, NPC, lore note. Combat encounters every 2-5 minutes.",
        "landmark_system": "Primary landmark: visible from 200m+ (tower, mountain, glowing tree). Secondary: visible from 50m (unique building, statue). Micro: 5m (campfire, glowing item).",
        "encounter_design": [
            "Ambient wildlife (passive until attacked)",
            "Patrol enemies (predictable path, teach stealth approach)",
            "Ambush (environmental cues: broken carts, blood trails)",
            "Defensible position (let player use terrain advantage)",
            "Roving boss (optional, runs away if player isn't ready — teaches fear/respect)",
        ],
        "playtesting_checklist": [
            "Did players find the main path without guidance?",
            "Did anyone wander in circles for >2 minutes?",
            "Were secrets satisfying to find (visual, audio, loot reward)?",
            "Can players navigate back to hub without fast travel?",
            "Are there 3+ distinct memorable locations in the area?",
        ],
    },
    "hub_world": {
        "principles": [
            "Central safe zone where all paths converge. Players memorize it.",
            "Visual distinct zones within hub: merchant area, quest board, crafting station, social space.",
            "Unlock over time: start small (3 rooms), expand as player progresses (new wings, NPCs arrive).",
            "NPCs with schedules: they move, talk, react. Makes the hub feel alive.",
            "Fast travel points at every exit. Players should never dread returning.",
            "Seasonal/event decorations: change hub for holidays, events, player milestones.",
        ],
        "flow_diagram": "Entrance -> Main Plaza (quest board + fast travel) -> Merchant Row -> Crafting District -> Guild Hall -> Player Housing -> Training Grounds",
        "pacing_guide": "Players spend 2-10 minutes in hub between missions. NPC dialogue should be snappy, menus fast. No unskippable animations.",
        "landmark_system": "Central statue/fountain as orientation point. Color-code districts: blue (water/magic), red (combat/forge), green (nature/alchemy), gold (commerce/quests).",
        "encounter_design": "No combat in hub. Optional minigames: target practice, fishing, card game, arena (separate instance).",
        "playtesting_checklist": [
            "Can players navigate to any service in <30 seconds?",
            "Are loading screens between hub zones? (should be zero)",
            "Does the hub feel alive with idle NPC animations and ambient sound?",
            "Can players express identity (housing, titles, cosmetics visible)?",
            "Do players linger (good) or rush through (bad)?",
        ],
    },
    "multiplayer_map": {
        "principles": [
            "Three-lane structure (classic MOBA/FPS): left flank, center, right flank.",
            "Power positions: high ground, cover, sightlines. Every position has a counter.",
            "Spawn safety: spawn areas must be unassailable. No spawn camping.",
            "Choke points + escape routes: every chokepoint needs at least one alternative path.",
            "Pickup/resource placement: contestable objectives in center, safer ones near spawn.",
            "Sightline control: long sightlines reward snipers, CQC areas reward shotguns. Mix both.",
        ],
        "flow_diagram": "Spawn A -> Safe lane -> Mid contest point -> Flank route -> Spawn B zone | Timed objectives drive rotation: 30s -> move to point, 60s -> fight, 90s -> new objective",
        "pacing_guide": "First engagement within 10s of leaving spawn. Objective captures every 30-45s. Match length 5-15 minutes.",
        "landmark_system": "Callout names on each zone: 'A site', 'bridge', 'tower', 'pit', 'elbow'. Map overlay with zone labels. Distinct visual identity per zone.",
        "encounter_design": [
            "Surprise engagement (corners, doors, drops)",
            "Long-range duel (bridge, corridor, rooftop)",
            "Objective contest (king of the hill, capture point)",
            "Resource fight (weapon spawn, power-up, ammo)",
            "Retreat/chase geometry (cover-spaced corridors, escape teleporters)",
        ],
        "playtesting_checklist": [
            "Is any spawn campable?",
            "Does one weapon/strategy dominate every engagement?",
            "Can players navigate without looking at minimap?",
            "Are matches consistently close (not one-sided stomps)?",
            "Is the map fun when losing (spectator, comeback potential)?",
        ],
    },
}

UNITY_SCAFFOLD = {
    "fps": {
        "directory_structure": [
            "Assets/Scripts/Player/",
            "Assets/Scripts/Weapons/",
            "Assets/Scripts/Enemies/",
            "Assets/Scripts/UI/",
            "Assets/Scripts/Managers/",
            "Assets/Prefabs/Player/",
            "Assets/Prefabs/Weapons/",
            "Assets/Prefabs/Enemies/",
            "Assets/Scenes/",
            "Assets/Materials/",
            "Assets/Textures/",
            "Assets/Audio/",
            "Assets/Animations/",
            "ProjectSettings/",
            "Packages/",
        ],
        "files": {
            "Assets/Scripts/Player/PlayerController.cs": textwrap.dedent(r"""
            using UnityEngine;

            [RequireComponent(typeof(CharacterController))]
            public class PlayerController : MonoBehaviour
            {
                [Header("Movement")]
                public float walkSpeed = 9f;
                public float sprintSpeed = 14f;
                public float jumpForce = 8f;
                public float gravity = 20f;
                public float mouseSensitivity = 2f;
                public float maxLookAngle = 80f;

                [Header("Ground Check")]
                public Transform groundCheck;
                public float groundDistance = 0.3f;
                public LayerMask groundMask;

                private CharacterController _controller;
                private Camera _playerCamera;
                private float _verticalRotation;
                private Vector3 _velocity;
                private bool _isGrounded;

                void Awake()
                {
                    _controller = GetComponent<CharacterController>();
                    _playerCamera = GetComponentInChildren<Camera>();
                    Cursor.lockState = CursorLockMode.Locked;
                    Cursor.visible = false;
                }

                void Update()
                {
                    HandleLook();
                    HandleMovement();
                    HandleJump();
                    HandleGravity();
                }

                void HandleLook()
                {
                    float mouseX = Input.GetAxis("Mouse X") * mouseSensitivity;
                    float mouseY = Input.GetAxis("Mouse Y") * mouseSensitivity;

                    _verticalRotation -= mouseY;
                    _verticalRotation = Mathf.Clamp(_verticalRotation, -maxLookAngle, maxLookAngle);

                    _playerCamera.transform.localRotation = Quaternion.Euler(_verticalRotation, 0f, 0f);
                    transform.Rotate(Vector3.up * mouseX);
                }

                void HandleMovement()
                {
                    float x = Input.GetAxis("Horizontal");
                    float z = Input.GetAxis("Vertical");
                    bool sprinting = Input.GetKey(KeyCode.LeftShift);

                    Vector3 move = transform.right * x + transform.forward * z;
                    float speed = sprinting ? sprintSpeed : walkSpeed;
                    _controller.Move(move * speed * Time.deltaTime);
                }

                void HandleJump()
                {
                    _isGrounded = Physics.CheckSphere(groundCheck.position, groundDistance, groundMask);
                    if (_isGrounded && _velocity.y < 0)
                        _velocity.y = -2f;

                    if (_isGrounded && Input.GetButtonDown("Jump"))
                        _velocity.y = Mathf.Sqrt(jumpForce * 2f * gravity);
                }

                void HandleGravity()
                {
                    _velocity.y -= gravity * Time.deltaTime;
                    _controller.Move(_velocity * Time.deltaTime);
                }
            }
            """).strip(),
            "Assets/Scripts/Weapons/Gun.cs": textwrap.dedent(r"""
            using UnityEngine;

            public class Gun : MonoBehaviour
            {
                public float damage = 25f;
                public float range = 100f;
                public float fireRate = 0.15f;
                public float recoilAmount = 2f;
                public int maxAmmo = 30;
                public float reloadTime = 1.5f;
                public ParticleSystem muzzleFlash;
                public GameObject impactEffect;
                public AudioSource fireSound;
                public AudioSource reloadSound;

                public Camera fpsCam;
                private float _nextFireTime;
                private int _currentAmmo;
                private bool _isReloading;

                void Start()
                {
                    _currentAmmo = maxAmmo;
                }

                void Update()
                {
                    if (_isReloading) return;

                    if (Input.GetButton("Fire1") && Time.time >= _nextFireTime && _currentAmmo > 0)
                    {
                        _nextFireTime = Time.time + fireRate;
                        Shoot();
                    }

                    if (Input.GetKeyDown(KeyCode.R) && _currentAmmo < maxAmmo)
                        StartCoroutine(Reload());
                }

                void Shoot()
                {
                    _currentAmmo--;
                    if (muzzleFlash) muzzleFlash.Play();
                    if (fireSound) fireSound.Play();

                    Vector3 shootDir = fpsCam.transform.forward;
                    shootDir += new Vector3(
                        Random.Range(-recoilAmount, recoilAmount) * 0.01f,
                        Random.Range(-recoilAmount, recoilAmount) * 0.01f,
                        0
                    );

                    if (Physics.Raycast(fpsCam.transform.position, shootDir, out RaycastHit hit, range))
                    {
                        if (hit.collider.TryGetComponent(out Target target))
                            target.TakeDamage(damage);

                        if (impactEffect)
                        {
                            GameObject impact = Instantiate(impactEffect, hit.point, Quaternion.LookRotation(hit.normal));
                            Destroy(impact, 2f);
                        }
                    }

                    if (_currentAmmo <= 0)
                        StartCoroutine(Reload());
                }

                System.Collections.IEnumerator Reload()
                {
                    _isReloading = true;
                    if (reloadSound) reloadSound.Play();
                    yield return new WaitForSeconds(reloadTime);
                    _currentAmmo = maxAmmo;
                    _isReloading = false;
                }
            }
            """).strip(),
            "Assets/Scripts/Enemies/Target.cs": textwrap.dedent(r"""
            using UnityEngine;

            public class Target : MonoBehaviour
            {
                public float health = 100f;
                public GameObject deathEffect;

                public void TakeDamage(float amount)
                {
                    health -= amount;
                    if (health <= 0f) Die();
                }

                void Die()
                {
                    if (deathEffect)
                    {
                        GameObject effect = Instantiate(deathEffect, transform.position, Quaternion.identity);
                        Destroy(effect, 2f);
                    }
                    Destroy(gameObject);
                }
            }
            """).strip(),
            "Assets/Scripts/Managers/GameManager.cs": textwrap.dedent(r"""
            using UnityEngine;
            using UnityEngine.SceneManagement;

            public class GameManager : MonoBehaviour
            {
                public static GameManager Instance { get; private set; }
                public int currentLevel = 0;
                public int score = 0;
                public bool isPaused;

                void Awake()
                {
                    if (Instance != null && Instance != this)
                    {
                        Destroy(gameObject);
                        return;
                    }
                    Instance = this;
                    DontDestroyOnLoad(gameObject);
                }

                public void LoadLevel(int levelIndex)
                {
                    currentLevel = levelIndex;
                    SceneManager.LoadSceneAsync(levelIndex);
                }

                public void AddScore(int points)
                {
                    score += points;
                }

                public void TogglePause()
                {
                    isPaused = !isPaused;
                    Time.timeScale = isPaused ? 0f : 1f;
                }
            }
            """).strip(),
            "Packages/manifest.json": json.dumps(
                {
                    "dependencies": {
                        "com.unity.cinemachine": "2.9.7",
                        "com.unity.inputsystem": "1.7.0",
                        "com.unity.render-pipelines.universal": "14.0.8",
                        "com.unity.textmeshpro": "3.0.6",
                    }
                },
                indent=2,
            ),
            ".gitignore": textwrap.dedent("""
            [Ll]ibrary/
            [Tt]emp/
            [Oo]bj/
            [Bb]uild/
            [Bb]uilds/
            [Ll]ogs/
            [Uu]ser[Ss]ettings/
            *.csproj
            *.sln
            *.unityproj
            *.pidb
            *.apk
            *.aab
            """).strip(),
        },
    },
}

UNREAL_SCAFFOLD = {
    "fps": {
        "directory_structure": [
            "Source/MyGame/",
            "Source/MyGame/Public/",
            "Source/MyGame/Private/",
            "Content/Maps/",
            "Content/Blueprints/",
            "Content/Characters/",
            "Content/Weapons/",
            "Content/UI/",
            "Content/Audio/",
            "Content/VFX/",
            "Config/",
        ],
        "files": {
            "Source/MyGame/Public/FPSCharacter.h": textwrap.dedent(r"""
            #pragma once

            #include "CoreMinimal.h"
            #include "GameFramework/Character.h"
            #include "FPSCharacter.generated.h"

            class UCameraComponent;
            class USkeletalMeshComponent;

            UCLASS()
            class MYGAME_API AFPSCharacter : public ACharacter
            {
                GENERATED_BODY()

            public:
                AFPSCharacter();

            protected:
                virtual void BeginPlay() override;
                virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

                void MoveForward(float Value);
                void MoveRight(float Value);
                void TurnAtRate(float Rate);
                void LookUpAtRate(float Rate);
                void StartJump();
                void StopJump();
                void StartFire();
                void StopFire();

                UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = Camera)
                UCameraComponent* FirstPersonCamera;

                UPROPERTY(VisibleDefaultsOnly, Category = Mesh)
                USkeletalMeshComponent* FPSMesh;

                UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Gameplay)
                float BaseTurnRate = 45.f;

                UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Gameplay)
                float BaseLookUpRate = 45.f;

                UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Combat)
                float WeaponRange = 10000.f;

                UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Combat)
                float WeaponDamage = 25.f;

                UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Combat)
                float FireRate = 0.15f;

                FTimerHandle FireTimerHandle;
                bool bIsFiring;

                void FireWeapon();
            };
            """).strip(),
            "Source/MyGame/Private/FPSCharacter.cpp": textwrap.dedent(r"""
            #include "FPSCharacter.h"
            #include "Camera/CameraComponent.h"
            #include "Components/SkeletalMeshComponent.h"
            #include "Components/InputComponent.h"
            #include "Engine/World.h"
            #include "DrawDebugHelpers.h"
            #include "Kismet/GameplayStatics.h"

            AFPSCharacter::AFPSCharacter()
            {
                PrimaryActorTick.bCanEverTick = true;

                FirstPersonCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
                FirstPersonCamera->SetupAttachment(GetRootComponent());
                FirstPersonCamera->bUsePawnControlRotation = true;

                FPSMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FPSMesh"));
                FPSMesh->SetupAttachment(FirstPersonCamera);
                FPSMesh->SetOnlyOwnerSee(true);
                FPSMesh->bCastDynamicShadow = false;

                bIsFiring = false;
            }

            void AFPSCharacter::BeginPlay()
            {
                Super::BeginPlay();
            }

            void AFPSCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
            {
                Super::SetupPlayerInputComponent(PlayerInputComponent);

                PlayerInputComponent->BindAxis("MoveForward", this, &AFPSCharacter::MoveForward);
                PlayerInputComponent->BindAxis("MoveRight", this, &AFPSCharacter::MoveRight);
                PlayerInputComponent->BindAxis("Turn", this, &AFPSCharacter::TurnAtRate);
                PlayerInputComponent->BindAxis("LookUp", this, &AFPSCharacter::LookUpAtRate);

                PlayerInputComponent->BindAction("Jump", IE_Pressed, this, &AFPSCharacter::StartJump);
                PlayerInputComponent->BindAction("Jump", IE_Released, this, &AFPSCharacter::StopJump);
                PlayerInputComponent->BindAction("Fire", IE_Pressed, this, &AFPSCharacter::StartFire);
                PlayerInputComponent->BindAction("Fire", IE_Released, this, &AFPSCharacter::StopFire);
            }

            void AFPSCharacter::MoveForward(float Value)
            {
                if (Value != 0.f)
                    AddMovementInput(GetActorForwardVector(), Value);
            }

            void AFPSCharacter::MoveRight(float Value)
            {
                if (Value != 0.f)
                    AddMovementInput(GetActorRightVector(), Value);
            }

            void AFPSCharacter::TurnAtRate(float Rate)
            {
                AddControllerYawInput(Rate * BaseTurnRate * GetWorld()->GetDeltaSeconds());
            }

            void AFPSCharacter::LookUpAtRate(float Rate)
            {
                AddControllerPitchInput(Rate * BaseLookUpRate * GetWorld()->GetDeltaSeconds());
            }

            void AFPSCharacter::StartJump() { Jump(); }
            void AFPSCharacter::StopJump() { StopJumping(); }

            void AFPSCharacter::StartFire()
            {
                bIsFiring = true;
                FireWeapon();
            }

            void AFPSCharacter::StopFire()
            {
                bIsFiring = false;
                GetWorldTimerManager().ClearTimer(FireTimerHandle);
            }

            void AFPSCharacter::FireWeapon()
            {
                FVector Start = FirstPersonCamera->GetComponentLocation();
                FVector Forward = FirstPersonCamera->GetForwardVector();
                FVector End = Start + (Forward * WeaponRange);

                FHitResult Hit;
                FCollisionQueryParams Params;
                Params.AddIgnoredActor(this);

                if (GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params))
                {
                    if (AActor* HitActor = Hit.GetActor())
                    {
                        UGameplayStatics::ApplyPointDamage(HitActor, WeaponDamage, Forward, Hit, GetController(), this, UDamageType::StaticClass());
                    }
                }

                if (bIsFiring)
                {
                    GetWorldTimerManager().SetTimer(FireTimerHandle, this, &AFPSCharacter::FireWeapon, FireRate, false);
                }
            }
            """).strip(),
            "Source/MyGame/MyGame.Build.cs": textwrap.dedent(r"""
            using UnrealBuildTool;

            public class MyGame : ModuleRules
            {
                public MyGame(ReadOnlyTargetRules Target) : base(Target)
                {
                    PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
                    PublicDependencyModuleNames.AddRange(new string[] {
                        "Core", "CoreUObject", "Engine", "InputCore",
                        "HeadMountedDisplay", "UMG", "AIModule"
                    });
                    PrivateDependencyModuleNames.AddRange(new string[] { });
                }
            }
            """).strip(),
            "Config/DefaultEngine.ini": textwrap.dedent(r"""
            [/Script/EngineSettings.GameMapsSettings]
            GameDefaultMap=/Game/Maps/MainMenu.MainMenu
            EditorStartupMap=/Game/Maps/MainMenu.MainMenu

            [/Script/Engine.RendererSettings]
            r.DefaultFeature.MotionBlur=False
            r.MotionBlurQuality=0
            r.DefaultFeature.AutoExposure.Method=0
            r.DynamicGlobalIlluminationMethod=1
            r.ReflectionMethod=1
            """).strip(),
            ".gitignore": textwrap.dedent("""
            Binaries/
            DerivedDataCache/
            Intermediate/
            Saved/
            .vs/
            *.VC.db
            *.opensdf
            *.sdf
            *.suo
            *.xcodeproj
            *.xcworkspace
            Build/
            *.target
            """).strip(),
        },
    },
}

ROBLOX_SCAFFOLD = {
    "fps": {
        "directory_structure": [
            "src/Server/",
            "src/Client/",
            "src/Shared/",
            "src/Server/Weapons/",
            "src/Server/Gameplay/",
            "src/Client/UI/",
            "src/Client/Effects/",
            "src/Shared/Types/",
        ],
        "files": {
            "src/Server/Gameplay/GameManager.server.lua": textwrap.dedent(r"""
            local ServerStorage = game:GetService("ServerStorage")
            local Players = game:GetService("Players")
            local ReplicatedStorage = game:GetService("ReplicatedStorage")
            local RunService = game:GetService("RunService")

            local Remotes = ReplicatedStorage:WaitForChild("Remotes")
            local DamageEvent = Remotes:WaitForChild("DamagePlayer")
            local RespawnEvent = Remotes:WaitForChild("RespawnPlayer")

            local GameManager = {}
            GameManager.Scores = {}
            GameManager.MatchActive = false

            function GameManager:StartMatch()
                self.MatchActive = true
                for _, player in ipairs(Players:GetPlayers()) do
                    self.Scores[player.UserId] = 0
                    self:SpawnPlayer(player)
                end
            end

            function GameManager:SpawnPlayer(player)
                local spawns = workspace:WaitForChild("SpawnPoints"):GetChildren()
                if #spawns == 0 then return end
                local spawn = spawns[math.random(1, #spawns)]

                player.CharacterAdded:Wait()
                local character = player.Character
                local humanoid = character:WaitForChild("Humanoid")

                local rootPart = character:WaitForChild("HumanoidRootPart")
                rootPart.CFrame = spawn.CFrame + Vector3.new(0, 3, 0)

                humanoid.Died:Connect(function()
                    self:OnPlayerDied(player)
                end)

                self:GiveLoadout(player)
            end

            function GameManager:GiveLoadout(player)
                local loadout = {
                    Weapons = {"Rifle", "Pistol"},
                    Health = 100,
                    Armor = 0,
                }
                local folder = Instance.new("Folder")
                folder.Name = "Loadout"
                folder.Parent = player
                for _, weaponName in ipairs(loadout.Weapons) do
                    local weapon = Instance.new("StringValue")
                    weapon.Name = weaponName
                    weapon.Parent = folder
                end
            end

            function GameManager:OnPlayerDied(player)
                self.Scores[player.UserId] = self.Scores[player.UserId] or 0
                task.wait(5)
                if self.MatchActive then
                    self:SpawnPlayer(player)
                end
            end

            DamageEvent.OnServerEvent:Connect(function(player, targetPlayer, damage)
                if not targetPlayer or not targetPlayer.Character then return end
                local humanoid = targetPlayer.Character:FindFirstChild("Humanoid")
                if humanoid and humanoid.Health > 0 then
                    humanoid:TakeDamage(damage)
                    if humanoid.Health <= 0 then
                        local killer = player
                        GameManager.Scores[killer.UserId] = (GameManager.Scores[killer.UserId] or 0) + 1
                    end
                end
            end)

            Players.PlayerAdded:Connect(function(player)
                GameManager.Scores[player.UserId] = 0
                if GameManager.MatchActive then
                    GameManager:SpawnPlayer(player)
                end
            end)

            return GameManager
            """).strip(),
            "src/Server/Weapons/Gun.server.lua": textwrap.dedent(r"""
            local ReplicatedStorage = game:GetService("ReplicatedStorage")
            local RunService = game:GetService("RunService")
            local Players = game:GetService("Players")

            local Remotes = ReplicatedStorage:WaitForChild("Remotes")
            local FireEvent = Remotes:WaitForChild("FireWeapon")
            local DamageEvent = Remotes:WaitForChild("DamagePlayer")

            local Gun = {}
            Gun.__index = Gun

            function Gun.new(config)
                local self = setmetatable({}, Gun)
                self.Damage = config.Damage or 25
                self.Range = config.Range or 500
                self.FireRate = config.FireRate or 0.15
                self.Ammo = config.Ammo or 30
                self.MaxAmmo = config.MaxAmmo or 30
                self.ReloadTime = config.ReloadTime or 1.5
                self.Recoil = config.Recoil or Vector3.new(0.5, 0.2, 0)
                self.LastFireTime = 0
                self.IsReloading = false
                return self
            end

            function Gun:CanFire()
                return tick() - self.LastFireTime >= self.FireRate
                    and self.Ammo > 0
                    and not self.IsReloading
            end

            function Gun:Fire(player, origin, direction)
                if not self:CanFire() then return end

                self.Ammo -= 1
                self.LastFireTime = tick()

                local recoil = Vector3.new(
                    math.random() * self.Recoil.X - self.Recoil.X / 2,
                    math.random() * self.Recoil.Y - self.Recoil.Y / 2,
                    0
                )
                direction = (direction + recoil).Unit

                local rayOrigin = origin
                local rayDirection = direction * self.Range

                local rayParams = RaycastParams.new()
                rayParams.FilterType = Enum.RaycastFilterType.Exclude
                rayParams.FilterDescendantsInstances = {player.Character}

                local rayResult = workspace:Raycast(rayOrigin, rayDirection, rayParams)
                if rayResult then
                    local hitInstance = rayResult.Instance
                    local hitCharacter = hitInstance:FindFirstAncestorOfClass("Model")
                    if hitCharacter then
                        local targetPlayer = Players:GetPlayerFromCharacter(hitCharacter)
                        if targetPlayer and targetPlayer ~= player then
                            DamageEvent:FireServer(targetPlayer, self.Damage)
                        end
                    end
                end

                if self.Ammo <= 0 then
                    self:Reload()
                end
            end

            function Gun:Reload()
                if self.IsReloading or self.Ammo == self.MaxAmmo then return end
                self.IsReloading = true
                task.wait(self.ReloadTime)
                self.Ammo = self.MaxAmmo
                self.IsReloading = false
            end

            FireEvent.OnServerEvent:Connect(function(player, origin, direction)
                local loadout = player:FindFirstChild("Loadout")
                if not loadout then return end
                local gun = loadout:FindFirstChild("CurrentGun")
                if not gun then return end
                require(script.Parent):Fire(player, origin, direction)
            end)

            return Gun
            """).strip(),
            "src/Client/UI/Scoreboard.client.lua": textwrap.dedent(r"""
            local Players = game:GetService("Players")
            local RunService = game:GetService("RunService")
            local LocalPlayer = Players.LocalPlayer

            local Scoreboard = {}
            local screenGui

            function Scoreboard:Create()
                screenGui = Instance.new("ScreenGui")
                screenGui.Name = "Scoreboard"
                screenGui.ResetOnSpawn = false
                screenGui.Parent = LocalPlayer:WaitForChild("PlayerGui")

                local frame = Instance.new("Frame")
                frame.Name = "Background"
                frame.Size = UDim2.new(0, 280, 0, 200)
                frame.Position = UDim2.new(1, -300, 0, 20)
                frame.AnchorPoint = Vector2.new(0, 0)
                frame.BackgroundTransparency = 0.4
                frame.BackgroundColor3 = Color3.fromRGB(20, 20, 20)
                frame.BorderSizePixel = 0
                frame.Parent = screenGui

                local title = Instance.new("TextLabel")
                title.Text = "SCOREBOARD"
                title.Size = UDim2.new(1, 0, 0, 30)
                title.BackgroundTransparency = 1
                title.TextColor3 = Color3.fromRGB(255, 255, 255)
                title.Font = Enum.Font.GothamBold
                title.TextSize = 18
                title.Parent = frame

                local listLayout = Instance.new("UIListLayout")
                listLayout.Padding = UDim.new(0, 4)
                listLayout.Parent = frame
            end

            return Scoreboard
            """).strip(),
            "rojo.json": json.dumps(
                {
                    "name": "MyGame",
                    "servePort": 8000,
                    "partitions": {
                        "src/Server": {"target": "ServerScriptService"},
                        "src/Client": {"target": "StarterPlayer.StarterPlayerScripts"},
                        "src/Shared": {"target": "ReplicatedStorage.Shared"},
                    },
                },
                indent=2,
            ),
            ".gitignore": textwrap.dedent("""
            *.rbxl
            *.rbxlx
            serve/
            build/
            """).strip(),
        },
    },
}


# ---------------------------------------------------------------------------
# Tool 1: Game Design Analysis
# ---------------------------------------------------------------------------


def _analyze_fun_factor(concept: str, genre: str) -> int:
    """Score fun-factor 0-100 based on genre alignment and concept strength."""
    score = 0
    genre_lower = genre.lower()
    concept_lower = concept.lower()

    if any(w in concept_lower for w in ["multiplayer", "co-op", "pvp", "social"]):
        score += 20
    if any(
        w in concept_lower for w in ["progression", "level up", "upgrade", "skill tree"]
    ):
        score += 20
    if any(
        w in concept_lower
        for w in ["unique", "innovative", "novel", "twist", "original"]
    ):
        score += 15
    if any(
        w in concept_lower for w in ["story", "narrative", "quest", "lore", "campaign"]
    ):
        score += 15
    if any(
        w in concept_lower for w in ["procedural", "random", "roguelike", "permadeath"]
    ):
        score += 15
    if any(
        w in concept_lower for w in ["competitive", "ranked", "esport", "leaderboard"]
    ):
        score += 10

    genre_data = GENRE_TAXONOMY.get(genre_lower)
    if genre_data:
        genre_keywords = genre_data["core_loop"].lower()
        match_count = sum(1 for w in concept_lower.split() if w in genre_keywords)
        score += min(match_count * 5, 20)

    return min(score, 100)


def _generate_engagement_loops(genre: str) -> str:
    """Generate engagement loop description for a genre."""
    genre_data = GENRE_TAXONOMY.get(genre.lower())
    if not genre_data:
        return "Core loop: Challenge -> Reward -> Progression -> Repeat"
    return genre_data["core_loop"]


def _find_similar_games(concept: str, genre: str) -> list:
    """Return similar notable games based on genre."""
    similar = []
    genre_lower = genre.lower()

    all_notables = []
    for engine in ENGINE_FEATURES.values():
        for game in engine["notable_games"]:
            if game not in all_notables:
                all_notables.append(game)

    sim_games = {
        "rpg": [
            "The Witcher 3",
            "Elden Ring",
            "Final Fantasy VII",
            "Persona 5",
            "Divinity: Original Sin 2",
        ],
        "fps": [
            "Call of Duty",
            "Doom Eternal",
            "Destiny 2",
            "Overwatch 2",
            "Counter-Strike 2",
        ],
        "puzzle": [
            "Portal 2",
            "The Witness",
            "Baba Is You",
            "Tetris Effect",
            "Monument Valley",
        ],
        "platformer": [
            "Celeste",
            "Super Mario Odyssey",
            "Hollow Knight",
            "Ori and the Will of the Wisps",
            "Cuphead",
        ],
        "sim": [
            "The Sims 4",
            "Cities: Skylines",
            "Stardew Valley",
            "Factorio",
            "Microsoft Flight Simulator",
        ],
        "strategy": [
            "Civilization VI",
            "XCOM 2",
            "Into the Breach",
            "Crusader Kings 3",
            "Age of Empires IV",
        ],
        "horror": [
            "Resident Evil 4",
            "Amnesia: The Dark Descent",
            "Phasmophobia",
            "Dead Space",
            "Silent Hill 2",
        ],
        "idle": [
            "Cookie Clicker",
            "Adventure Capitalist",
            "Egg, Inc.",
            "Idle Heroes",
            "Melvor Idle",
        ],
        "roguelike": [
            "Hades",
            "Slay the Spire",
            "Dead Cells",
            "The Binding of Isaac",
            "Risk of Rain 2",
        ],
        "social": ["Animal Crossing", "VRChat", "Among Us", "Fall Guys", "Roblox"],
    }
    return sim_games.get(genre_lower, all_notables[:5])


def gamedev_design_analyze(concept: str, genre: str, platform: str = "pc") -> dict:
    """
    Analyze a game concept for fun-factor, engagement, and profitability.
    Returns score, strengths, weaknesses, engagement loops, monetization fit, market position, similar games.
    """
    try:
        genre_lower = genre.lower()
        genre_data = GENRE_TAXONOMY.get(genre_lower)
        if not genre_data:
            valid_genres = list(GENRE_TAXONOMY.keys())
            return {
                "status": "error",
                "error": f"Unknown genre '{genre}'. Valid: {valid_genres}",
            }

        fun_score = _analyze_fun_factor(concept, genre)
        engagement = _generate_engagement_loops(genre)
        similar = _find_similar_games(concept, genre)

        strengths = []
        weaknesses = []
        concept_lower = concept.lower()

        if any(w in concept_lower for w in ["unique", "innovative", "original"]):
            strengths.append("Unique hook: stands out in the market")
            weaknesses.append(
                "Untested concept may require more playtesting to validate"
            )

        if any(w in concept_lower for w in ["multiplayer", "co-op"]):
            strengths.append(
                "Multiplayer extends lifetime value and enables viral growth"
            )
            weaknesses.append(
                "Multiplayer requires server infrastructure, matchmaking, and moderation"
            )

        if any(w in concept_lower for w in ["story", "narrative"]):
            strengths.append("Narrative focus drives emotional investment")
            weaknesses.append("Linear story limits replayability without branching")

        if platform == "mobile":
            strengths.append(
                "Mobile platform reaches largest gaming audience (2.8B+ players)"
            )
            weaknesses.append(
                "Mobile discoverability is dominated by App Store/Google Play algorithms"
            )
        elif platform == "console":
            strengths.append(
                "Console players have higher willingness to pay premium prices"
            )
            weaknesses.append(
                "Console certification process adds 2-4 weeks to each update"
            )
        elif platform == "vr":
            strengths.append("VR market growing at 27% CAGR, less saturated")
            weaknesses.append("VR install base still small (~34M devices)")

        if genre_lower in ["idle", "puzzle"]:
            strengths.append(
                f"{genre.title()} games have low development cost and high margin"
            )
        elif genre_lower in ["rpg", "sim"]:
            strengths.append(
                f"{genre.title()} genre supports deep monetization via expansions/IAP"
            )
        else:
            strengths.append(
                f"{genre.title()} is an established genre with proven monetization models"
            )

        monetization_fit = genre_data.get("revenue_models", [])
        retention = genre_data.get("retention_drivers", [])

        market_position = f"{genre.title()} on {platform}. Retention driven by {', '.join(retention[:2])}. "
        market_position += f"Monetize via {monetization_fit[0].replace('_', ' ')}."

        return {
            "status": "ok",
            "score": fun_score,
            "strengths": strengths or ["Clear genre fit", "Proven engagement model"],
            "weaknesses": weaknesses
            or [
                "Needs more specific differentiation",
                "Market may be saturated for this genre",
            ],
            "engagement_loops": engagement,
            "monetization_fit": ", ".join(monetization_fit[:3]).replace("_", " "),
            "market_position": market_position,
            "similar_games": similar,
            "retention_drivers": retention,
            "recommended_session_length": genre_data.get("avg_session", "varies"),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Tool 2: Project Scaffolding
# ---------------------------------------------------------------------------


def _unity_scaffold_fps(name: str) -> dict:
    scaffold = UNITY_SCAFFOLD["fps"]
    files = dict(scaffold["files"])
    files["Assets/Scenes/MainScene.unity.meta"] = "fileFormatVersion: 2\nguid: " + str(
        abs(hash(name)) % (10**32)
    ).zfill(32)
    files["ProjectSettings/ProjectVersion.txt"] = "m_EditorVersion: 2022.3.0f1"
    return {
        "project_name": name,
        "directory_structure": list(scaffold["directory_structure"]),
        "files": files,
    }


def _unreal_scaffold_fps(name: str) -> dict:
    scaffold = UNREAL_SCAFFOLD["fps"]
    files = dict(scaffold["files"])
    files[f"{name}.uproject"] = json.dumps(
        {
            "FileVersion": 3,
            "EngineAssociation": "5.3",
            "Category": "Game",
            "Description": f"{name} - FPS Game",
            "Modules": [{"Name": name, "Type": "Runtime", "LoadingPhase": "Default"}],
        },
        indent=2,
    )
    return {
        "project_name": name,
        "directory_structure": list(scaffold["directory_structure"]),
        "files": files,
    }


def _roblox_scaffold_fps(name: str) -> dict:
    scaffold = ROBLOX_SCAFFOLD["fps"]
    files = dict(scaffold["files"])
    files["src/Shared/Types/WeaponConfig.lua"] = textwrap.dedent("""
    return {
        Rifle = { Damage = 25, FireRate = 0.1, Ammo = 30, Range = 500, ReloadTime = 1.5 },
        Pistol = { Damage = 15, FireRate = 0.25, Ammo = 12, Range = 200, ReloadTime = 1.0 },
        Shotgun = { Damage = 80, FireRate = 0.8, Ammo = 6, Range = 100, ReloadTime = 2.0, Pellets = 8 },
        Sniper = { Damage = 120, FireRate = 1.2, Ammo = 5, Range = 2000, ReloadTime = 2.5 },
    }
    """).strip()
    return {
        "project_name": name,
        "directory_structure": list(scaffold["directory_structure"]),
        "files": files,
    }


def gamedev_scaffold_project(
    engine: str, genre: str, name: str = "MyGame", features: Any = None
) -> dict:
    """
    Generate a complete game project scaffold with real code files.
    Returns project_name, directory_structure, files dict, setup_instructions, recommended_assets.
    """
    try:
        if features is None:
            features = []
        engine_lower = engine.lower()
        genre_lower = genre.lower()

        setup_instructions = ""
        recommended_assets = []

        if engine_lower == "unity":
            result = _unity_scaffold_fps(name)
            setup_instructions = "1. Open Unity Hub, click 'Add', select the project folder.\n2. Unity will generate Library/ and other folders automatically.\n3. Open MainScene in Assets/Scenes/.\n4. Press Play to test the PlayerController.\n5. Install packages from Package Manager: Cinemachine, Input System, URP."
            recommended_assets = [
                "Standard Assets (Unity)",
                "Cinemachine",
                "TextMeshPro",
                "URP sample assets",
            ]
        elif engine_lower == "unreal":
            result = _unreal_scaffold_fps(name)
            setup_instructions = f"1. Right-click {name}.uproject > Generate Visual Studio project files.\n2. Open {name}.uproject in Unreal Editor.\n3. Compile C++ code in editor (or build from VS).\n4. Create Blueprint child of FPSCharacter: right-click > Create Blueprint Class.\n5. Add input mappings in Project Settings > Input."
            recommended_assets = [
                "Epic Games Starter Content",
                "Quixel Megascans",
                "Lyra Starter Game",
                "ALS (Advanced Locomotion System)",
            ]
        elif engine_lower == "roblox":
            result = _roblox_scaffold_fps(name)
            setup_instructions = "1. Install Rojo: `cargo install rojo` or download from GitHub.\n2. Run `rojo serve` in project folder.\n3. Install Rojo plugin in Roblox Studio.\n4. Connect plugin to localhost:8000.\n5. All scripts sync automatically."
            recommended_assets = [
                "Roblox Studio built-in toolbox",
                "RigEdit Lite plugin",
                "Moon Animator",
                "Material Generator plugin",
            ]
        elif engine_lower == "godot":
            result = {
                "project_name": name,
                "directory_structure": [
                    "src/player/",
                    "src/enemies/",
                    "src/weapons/",
                    "src/ui/",
                    "src/levels/",
                    "assets/textures/",
                    "assets/audio/",
                    "assets/models/",
                ],
                "files": {
                    "src/player/player.gd": textwrap.dedent(r"""
                    extends CharacterBody3D
                    @export var walk_speed := 9.0
                    @export var sprint_speed := 14.0
                    @export var jump_velocity := 8.0
                    @export var mouse_sensitivity := 0.002
                    @export var max_look_angle := 80.0
                    var gravity := ProjectSettings.get_setting("physics/3d/default_gravity")
                    var vertical_rotation := 0.0
                    func _ready():
                        Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
                    func _input(event):
                        if event is InputEventMouseMotion:
                            rotate_y(-event.relative.x * mouse_sensitivity)
                            vertical_rotation -= event.relative.y * mouse_sensitivity
                            vertical_rotation = clamp(vertical_rotation, deg_to_rad(-max_look_angle), deg_to_rad(max_look_angle))
                            $Camera3D.rotation.x = vertical_rotation
                    func _physics_process(delta):
                        if not is_on_floor():
                            velocity.y -= gravity * delta
                        if Input.is_action_just_pressed("ui_accept") and is_on_floor():
                            velocity.y = jump_velocity
                        var input_dir := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
                        var direction := (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()
                        var speed := sprint_speed if Input.is_key_pressed(KEY_SHIFT) else walk_speed
                        velocity.x = direction.x * speed
                        velocity.z = direction.z * speed
                        move_and_slide()
                    """).strip(),
                    "project.godot": textwrap.dedent("""
                    config_version=5
                    [application]
                    config/name="MyGame"
                    config/features=PackedStringArray("4.3", "Forward Plus")
                    [input]
                    move_forward={"deadzone": 0.5, "events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":87,"key_label":0,"unicode":0,"echo":false,"script":null)]}
                    move_back={"deadzone": 0.5, "events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":83,"key_label":0,"unicode":0,"echo":false,"script":null)]}
                    """).strip(),
                },
            }
            setup_instructions = "1. Open Godot 4.3+.\n2. Import the project.godot file.\n3. Open the main scene or create one from the player scene.\n4. Press F5 to run."
            recommended_assets = [
                "Godot Asset Library",
                "Kenney.nl assets",
                "GDQuest plugins",
            ]
        else:
            return {
                "status": "error",
                "error": f"Unknown engine: {engine}. Choose: unity, unreal, roblox, godot",
            }

        result["setup_instructions"] = setup_instructions
        result["recommended_assets"] = recommended_assets
        result["engine"] = engine
        result["genre"] = genre
        result["status"] = "ok"
        return result

    except Exception as e:
        return {"status": "error", "error": str(e), "engine": engine}


# ---------------------------------------------------------------------------
# Tool 3: Mechanics Guide
# ---------------------------------------------------------------------------


def gamedev_mechanics_guide(genre: str, complexity: str = "core") -> dict:
    """
    Design game mechanics for a specific genre and complexity level.
    Returns core_loop, mechanic_systems, progression_system, reward_schedule, balance_considerations.
    """
    try:
        genre_lower = genre.lower()
        genre_data = GENRE_TAXONOMY.get(genre_lower)
        if not genre_data:
            return {
                "status": "error",
                "error": f"Unknown genre: {genre}. Valid: {list(GENRE_TAXONOMY.keys())}",
            }

        mechanics_db = {
            "rpg": {
                "casual": [
                    {
                        "name": "Auto-battle",
                        "description": "Characters fight automatically. Player manages gear and formation.",
                        "fun_factor": 5,
                        "implementation_tips": "Use simple rock-paper-scissors element system. Three formation slots.",
                    },
                    {
                        "name": "Gacha collection",
                        "description": "Random character acquisition via pulls. Collect to fill roster.",
                        "fun_factor": 8,
                        "implementation_tips": "Implement pity system (guaranteed rare after 50 pulls). Show rates transparently.",
                    },
                    {
                        "name": "Daily quest system",
                        "description": "5-6 daily tasks that reset. Kill X, collect Y, upgrade Z.",
                        "fun_factor": 6,
                        "implementation_tips": "Auto-navigate to quest locations. Show progress bar. Stack rewards for streak.",
                    },
                    {
                        "name": "Merge/craft gear",
                        "description": "Combine 3 identical items to create higher rarity version.",
                        "fun_factor": 7,
                        "implementation_tips": "Use a simple merge board UI. Animate the merge with particle effects.",
                    },
                ],
                "core": [
                    {
                        "name": "Real-time combat with pause",
                        "description": "Active combat where player can pause to issue tactical commands.",
                        "fun_factor": 8,
                        "implementation_tips": "Implement action queue system. Show threat indicators on enemies. Use ability cooldown UI circles.",
                    },
                    {
                        "name": "Deep skill tree",
                        "description": "Branching specialization paths: 3-5 branches, 20-30 nodes each.",
                        "fun_factor": 9,
                        "implementation_tips": "Allow respec at checkpoints. Visualize branch paths like a tree. Gate powerful nodes behind prerequisites.",
                    },
                    {
                        "name": "Party system (4 characters)",
                        "description": "Control a party of 4. Each has unique class abilities. Switch during combat.",
                        "fun_factor": 9,
                        "implementation_tips": "AI controls non-active party members. Use gambit system (if HP <30%, cast Heal) for AI behavior. Quick-switch keys.",
                    },
                    {
                        "name": "Elemental weakness system",
                        "description": "Fire > Ice > Earth > Lightning > Fire. Exploit for 2x damage.",
                        "fun_factor": 7,
                        "implementation_tips": "Show effectiveness text on hit (Super Effective!). Color code elements. Teach through early-game tutorial enemies.",
                    },
                ],
                "hardcore": [
                    {
                        "name": "Permadeath mode",
                        "description": "Party members die permanently. No revival. Replacement characters must be recruited.",
                        "fun_factor": 7,
                        "implementation_tips": "Allow escape from any battle. Show danger ratings before encounters. Memorial hall for fallen party members.",
                    },
                    {
                        "name": "Complex crafting with quality tiers",
                        "description": "Materials have quality (1-5 star). Higher quality = better results. Chance to fail at low skill.",
                        "fun_factor": 6,
                        "implementation_tips": "Show probability before craft. Allow boosting with rare catalysts. Skill levels up with use (like Skyrim).",
                    },
                    {
                        "name": "Moral choice consequences",
                        "description": "Decisions lock/unlock quest lines, companions, endings. No take-backs.",
                        "fun_factor": 8,
                        "implementation_tips": "Write at least 3 divergent paths per major decision. Track karma-like score. Show consequences hours later, not immediately.",
                    },
                ],
            },
            "fps": {
                "casual": [
                    {
                        "name": "Aim assist (sticky aim)",
                        "description": "Reticle slows down when passing over enemies. Reduces skill floor.",
                        "fun_factor": 6,
                        "implementation_tips": "Adjustable strength slider. Reduce assist at close range. Visual feedback when assist is active.",
                    },
                    {
                        "name": "Regenerating health",
                        "description": "HP recovers after 5s out of combat. No health packs needed.",
                        "fun_factor": 6,
                        "implementation_tips": "Show regen HUD indicator. Differentiate between combat damage and environmental damage. Regenerates shield first, then health.",
                    },
                    {
                        "name": "Simple weapon wheel",
                        "description": "3 weapons max. Scroll/button to swap. Each has ammo count.",
                        "fun_factor": 7,
                        "implementation_tips": "Slow-motion during weapon swap. Show ammo on wheel. Auto-switch to pistol when primary empty.",
                    },
                ],
                "core": [
                    {
                        "name": "ADS (Aim Down Sights)",
                        "description": "Right-click zooms weapon. Reduces spread, slows movement. Core FPS mechanic.",
                        "fun_factor": 8,
                        "implementation_tips": "Smooth FOV transition (80 -> 60). Sway animation on long ADS. Breath-hold mechanic for snipers.",
                    },
                    {
                        "name": "Slide, vault, mantling",
                        "description": "Sprint + crouch = slide. Jump near ledge = climb up. Obstacle = vault over.",
                        "fun_factor": 9,
                        "implementation_tips": "Use animation blending for smooth transitions. Cancel slide into jump for speed boost. Detect ledge height automatically.",
                    },
                    {
                        "name": "Killstreak rewards",
                        "description": "3 kills = UAV (see enemies on minimap). 5 = airstrike. 7 = attack helicopter.",
                        "fun_factor": 9,
                        "implementation_tips": "Announce killstreaks to all players. Streak resets on death. Make rewards powerful but counterable.",
                    },
                ],
                "hardcore": [
                    {
                        "name": "Realistic ballistics",
                        "description": "Bullet drop, travel time, wind. No hitscan. Zero at 100m.",
                        "fun_factor": 6,
                        "implementation_tips": "Show bullet trail. Mildot scope reticles. Practice range with moving targets required.",
                    },
                    {
                        "name": "Limited HUD (hardcore mode)",
                        "description": "No minimap, no ammo counter, no crosshair. Must count shots and navigate by landmarks.",
                        "fun_factor": 5,
                        "implementation_tips": "Weapon has visible ammo (transparent mag). Compass only. Audio cues for low ammo (clicking when empty).",
                    },
                    {
                        "name": "Friendly fire always on",
                        "description": "Shoot teammates = damage them. Requires trigger discipline and communication.",
                        "fun_factor": 4,
                        "implementation_tips": "Distinct team uniforms/silhouettes. Punish team-killers (kick after 3 TKs). Forgive system for accidental kills.",
                    },
                ],
            },
            "roguelike": {
                "casual": [
                    {
                        "name": "Meta-progression currency",
                        "description": "Die -> earn souls -> spend on permanent upgrades -> next run is easier.",
                        "fun_factor": 8,
                        "implementation_tips": "Show what each upgrade unlocks. Expensive upgrades give run-changing abilities. Always feel progression even on death.",
                    },
                    {
                        "name": "Simple buff stacking",
                        "description": "Pick 1 of 3 random buffs after clearing a room. Buffs stack through the run.",
                        "fun_factor": 9,
                        "implementation_tips": "Categorize buffs: offensive (red), defensive (blue), utility (green). Show stacked effects on HUD. Allow synergy bonuses.",
                    },
                ],
                "core": [
                    {
                        "name": "Procedural room generation",
                        "description": "Rooms are hand-designed but arranged randomly. Connectors are procedural corridors.",
                        "fun_factor": 9,
                        "implementation_tips": "Create 30+ room templates. Weight room types: 40% combat, 25% reward, 15% shop, 10% event, 10% boss entrance.",
                    },
                    {
                        "name": "Synergy-based builds",
                        "description": "Items that combo: 'fire damage + enemies explode on death = screen-clearing chain reaction'.",
                        "fun_factor": 10,
                        "implementation_tips": "Tag all items with categories (fire, lightning, summon, crit). Show synergy bonus when 2+ related items equipped. Design 15+ synergistic combos.",
                    },
                    {
                        "name": "Risk/reward branching",
                        "description": "Easy path (fewer rewards) vs hard path (better loot but dangerous). Player chooses at forks.",
                        "fun_factor": 9,
                        "implementation_tips": "Show difficulty indicator (skulls). Preview possible reward type (weapon, item, currency). Narrow escape routes on hard paths.",
                    },
                ],
            },
        }

        genre_mechanics = mechanics_db.get(genre_lower, {})
        complexity_key = complexity.lower()
        if complexity_key == "hardcore" and "hardcore" not in genre_mechanics:
            complexity_key = "core"
        if complexity_key not in genre_mechanics:
            complexity_key = "core"

        systems = genre_mechanics.get(
            complexity_key,
            [
                {
                    "name": "Core action",
                    "description": genre_data["core_loop"],
                    "fun_factor": 7,
                    "implementation_tips": "Focus on responsive controls and clear feedback",
                }
            ],
        )

        fallback_progression = "Linear level progression with difficulty scaling"
        fallback_rewards = "Every 60-90 seconds: small reward. Every 5 minutes: medium reward. Every 15 minutes: major reward."

        genre_progressions = {
            "rpg": "Level 1-50: unlock core abilities by level 15. Specialization choice at 20. Legendary skills at 40+. Side quests scale with main story progress.",
            "fps": "Level 1: unlock all base weapons. Rank unlocks: camos, attachments, perks. Prestige system: reset for exclusive cosmetics. Battle pass tiers 1-100 per season.",
            "roguelike": "Meta-progression: persistent upgrades between runs (unlock new items, characters, starting bonuses). Run progression: items, stats, abilities within a single run.",
            "idle": "Earn currency per second. Tier 1-10 upgrades with 10x cost increase each. Prestige at level 100: reset but earn prestige currency. Next prestige at 120, then 150...",
            "sim": "Tiered milestones: build first X, unlock Y. Tech tree: research new capabilities. Prestige/expansion: new area/map unlocks after milestones.",
            "puzzle": "World 1-10 levels each, 3 stars per level. Gates: need X stars to unlock next world. Power-ups unlockable with stars. Daily challenge: 1 new puzzle per day.",
        }

        genre_rewards = {
            "idle": "Logarithmic reward curve. Numbers go up every tick. Exponential milestones (1K -> 1M -> 1B -> 1T). Prestige doubles speed.",
            "roguelike": "Room clear = small reward. Boss kill = major item. Secret room = legendary. Final boss = unlock new character/starting item.",
            "rpg": "Quest completion = XP + gold. Boss drop = rare gear. Exploration = lore journal + XP. Daily login = currency. Streak = bonus currency.",
        }

        progression = genre_progressions.get(genre_lower, fallback_progression)
        rewards = genre_rewards.get(genre_lower, fallback_rewards)

        balance_considerations = [
            "Vary difficulty dynamically: if player dies 3+ times at same spot, subtly reduce enemy HP/damage by 10%.",
            "Economy balance: players should earn enough currency to buy 1-2 meaningful upgrades per hour.",
            "Build diversity: no single strategy should dominate. If >60% of players use the same build, nerf or buff alternatives.",
            "First-time user experience (FTUE): first 30 minutes must be 90%+ completion rate. Tutorial can't lose players.",
            "Power creep: each new content update should not make old content trivial. Use horizontal progression (more options, not strictly better).",
        ]

        return {
            "status": "ok",
            "core_loop": genre_data["core_loop"],
            "mechanic_systems": systems,
            "progression_system": progression,
            "reward_schedule": rewards,
            "balance_considerations": balance_considerations,
            "genre": genre,
            "complexity": complexity_key,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Tool 4: Monetization Strategy
# ---------------------------------------------------------------------------


def gamedev_monetization(
    platform: str = "mobile", genre: str = "puzzle", audience: str = "casual"
) -> dict:
    """
    Recommend monetization strategies based on platform, genre, and audience.
    Returns primary_strategy, secondary_strategies, price_points, ad_format, ethical_considerations, revenue_estimates.
    """
    try:
        platform_lower = platform.lower()
        genre_lower = genre.lower()
        audience_lower = audience.lower()

        genre_data = GENRE_TAXONOMY.get(genre_lower, GENRE_TAXONOMY["puzzle"])
        revenue_models = genre_data.get("revenue_models", ["premium"])

        primary = (
            revenue_models[0].replace("_", " ").title() if revenue_models else "Premium"
        )
        secondary = [m.replace("_", " ").title() for m in revenue_models[1:4]]

        price_points = []
        if platform_lower == "mobile":
            price_points = [
                "$0.99 (sale price)",
                "$4.99 (standard mobile)",
                "$9.99 (premium mobile)",
                "$2.99/week subscription",
                "$7.99/month subscription",
            ]
        elif platform_lower in ("pc", "console"):
            price_points = [
                "$14.99 (indie)",
                "$29.99 (AA)",
                "$59.99-$69.99 (AAA)",
                "$9.99 battle pass / season",
                "$4.99/month subscription",
            ]
        elif platform_lower == "roblox":
            price_points = [
                "25-100 Robux ($0.25-$1.00) per cosmetic",
                "500-2000 Robux ($5-$20) for game passes / permanent unlocks",
                "50-200 Robux ($0.50-$2.00) per consumable / boost",
            ]

        ad_format = (
            "Rewarded video ads (30s watch = in-game reward)"
            if platform_lower == "mobile"
            else "N/A (premium/battle pass model)"
        )

        ethical_considerations = [
            "Disclose all drop rates (percentages) for any random reward mechanics.",
            "Implement spending limits: daily cap, confirmation for purchases >$50.",
            "Separate progression items from pay-only items: all game-affecting items should be earnable through gameplay.",
            "No manipulative dark patterns: no 'pay to continue', no hidden recurring charges, easy cancellation.",
            "Avoid targeting children with gacha/gambling-style mechanics (COPPA/GDPR compliance).",
        ]

        arpu_estimates = {
            "mobile": {
                "casual": "$0.10-$0.50/month",
                "core": "$1-$5/month",
                "hardcore": "$5-$20/month",
            },
            "pc": {
                "casual": "$0.50-$2/month",
                "core": "$2-$10/month",
                "hardcore": "$10-$50/month",
            },
            "console": {
                "casual": "$1-$3/month",
                "core": "$3-$15/month",
                "hardcore": "$15-$60/month",
            },
            "roblox": {
                "casual": "$0.05-$0.20/visit",
                "core": "$0.20-$1/visit",
                "hardcore": "$1-$5/visit",
            },
        }
        arpu = arpu_estimates.get(platform_lower, arpu_estimates["mobile"]).get(
            audience_lower, "$1-$5/month"
        )

        conversion = (
            "2-5% (freemium)"
            if "freemium" in revenue_models or "free" in str(revenue_models)
            else "100% (premium: all users pay)"
        )

        return {
            "status": "ok",
            "primary_strategy": primary,
            "secondary_strategies": secondary,
            "price_points": price_points,
            "ad_format_recommendation": ad_format,
            "ethical_considerations": ethical_considerations,
            "revenue_estimates": {
                "arpu": arpu,
                "conversion_rate": conversion,
                "note": "Estimates are industry averages. Actual results vary by execution, marketing, and market conditions.",
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Tool 5: Optimization Advice
# ---------------------------------------------------------------------------


def gamedev_optimization(engine: str, issue: str) -> dict:
    """
    Engine-specific optimization advice for common performance issues.
    Returns diagnosis, solutions, profiling_tools, common_pitfalls.
    """
    try:
        engine_lower = engine.lower()
        issue_lower = issue.lower()
        engine_data = ENGINE_OPTIMIZATION.get(engine_lower)
        if not engine_data:
            return {
                "status": "error",
                "error": f"Engine '{engine}' not supported. Try: unity, unreal, roblox, godot",
            }

        issue_map = {
            "low_fps": "low_fps",
            "lowfps": "low_fps",
            "fps": "low_fps",
            "draw_calls": "draw_calls",
            "drawcalls": "draw_calls",
            "draw": "draw_calls",
            "memory": "memory",
            "ram": "memory",
            "oom": "memory",
            "load_times": "load_times",
            "loadtimes": "load_times",
            "loading": "load_times",
            "network_lag": "network_lag",
            "networklag": "network_lag",
            "network": "network_lag",
            "lag": "network_lag",
            "build_size": "build_size",
            "buildsize": "build_size",
            "size": "build_size",
        }
        match_key = issue_map.get(issue_lower)
        if not match_key:
            return {
                "status": "error",
                "error": f"Issue '{issue}' not recognized. Try: low_fps, draw_calls, memory, load_times, network_lag, build_size",
            }

        issue_data = engine_data.get(match_key)
        if not issue_data:
            available = list(engine_data.keys())
            return {
                "status": "error",
                "error": f"Issue '{issue}' not available for {engine}. Available: {available}",
            }

        return {
            "status": "ok",
            "engine": engine,
            "issue": match_key,
            "diagnosis": issue_data["diagnosis"],
            "solutions": issue_data["solutions"],
            "profiling_tools": issue_data["profiling_tools"],
            "common_pitfalls": issue_data["common_pitfalls"],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Tool 6: Compare Engines
# ---------------------------------------------------------------------------


def gamedev_compare_engines(
    project_type: str, team_size: str = "small", budget: str = "indie"
) -> dict:
    """
    Compare game engines for a specific project type.
    Returns recommendation, comparison table, and verdict.
    """
    try:
        engines = ["unity", "unreal", "godot", "roblox"]
        comparison = {}

        for engine_name in engines:
            eng = ENGINE_FEATURES[engine_name]
            fit = 50

            if project_type in ("2d", "2D", "2d_game", "2d_platformer"):
                if engine_name == "godot":
                    fit = 95
                elif engine_name == "unity":
                    fit = 85
                elif engine_name == "unreal":
                    fit = 40
                elif engine_name == "roblox":
                    fit = 50

            elif project_type in ("3d_open_world", "open_world"):
                if engine_name == "unreal":
                    fit = 95
                elif engine_name == "unity":
                    fit = 70
                elif engine_name == "godot":
                    fit = 35
                elif engine_name == "roblox":
                    fit = 20

            elif project_type in ("fps", "first_person", "shooter"):
                if engine_name == "unreal":
                    fit = 90
                elif engine_name == "unity":
                    fit = 80
                elif engine_name == "godot":
                    fit = 50
                elif engine_name == "roblox":
                    fit = 60

            elif project_type in ("mobile", "mobile_game"):
                if engine_name == "unity":
                    fit = 92
                elif engine_name == "godot":
                    fit = 60
                elif engine_name == "unreal":
                    fit = 35
                elif engine_name == "roblox":
                    fit = 30

            elif project_type in ("social", "social_experience", "ugc"):
                if engine_name == "roblox":
                    fit = 95
                elif engine_name == "unity":
                    fit = 45
                elif engine_name == "unreal":
                    fit = 40
                elif engine_name == "godot":
                    fit = 30

            elif project_type in ("vr", "ar", "xr"):
                if engine_name == "unity":
                    fit = 88
                elif engine_name == "unreal":
                    fit = 80
                elif engine_name == "godot":
                    fit = 30
                elif engine_name == "roblox":
                    fit = 25

            elif project_type == "":
                pass
            else:
                if engine_name == "unity":
                    fit = 75
                elif engine_name == "unreal":
                    fit = 70
                elif engine_name == "godot":
                    fit = 55
                elif engine_name == "roblox":
                    fit = 40

            if team_size == "solo":
                if engine_name == "godot":
                    fit += 10
                elif engine_name == "roblox":
                    fit += 5
                if engine_name == "unreal":
                    fit -= 15
            elif team_size == "large":
                if engine_name == "unreal":
                    fit += 10
                if engine_name == "godot":
                    fit -= 5
                if engine_name == "roblox":
                    fit -= 5

            if budget == "none":
                if engine_name in ("godot", "roblox"):
                    fit += 10
            elif budget in ("aa", "aaa"):
                if engine_name == "unreal":
                    fit += 10
                if engine_name == "unity":
                    fit += 5

            fit = max(0, min(100, fit))

            comparison[engine_name] = {
                "pros": eng["strengths"][:4],
                "cons": eng["weaknesses"][:3],
                "fit_score": fit,
                "best_for": eng["best_for"],
                "learning_curve": eng["learning_curve"],
            }

        best = max(comparison, key=lambda e: comparison[e]["fit_score"])
        best_data = comparison[best]
        second_best = sorted(
            comparison, key=lambda e: comparison[e]["fit_score"], reverse=True
        )[1]

        return {
            "status": "ok",
            "recommendation": best,
            "comparison": comparison,
            "verdict": (
                f"{best.title()} is the best fit (score: {best_data['fit_score']}/100). "
                f"Its strengths ({', '.join(best_data['pros'][:2]).lower()}) align well with "
                f"{project_type} development. {second_best.title()} is the runner-up "
                f"({comparison[second_best]['fit_score']}/100)."
            ),
            "project_type": project_type,
            "team_size": team_size,
            "budget": budget,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Tool 7: Level Design
# ---------------------------------------------------------------------------


def gamedev_level_design(genre: str, level_type: str) -> dict:
    """
    Level design principles and patterns for a specific genre and level type.
    Returns principles, flow_diagram, pacing_guide, landmark_system, encounter_design, playtesting_checklist.
    """
    try:
        design = GAME_LEVEL_DESIGN.get(level_type.lower())
        if not design:
            valid_types = list(GAME_LEVEL_DESIGN.keys())
            return {
                "status": "error",
                "error": f"Unknown level type: {level_type}. Valid: {valid_types}",
            }

        return {
            "status": "ok",
            "genre": genre,
            "level_type": level_type,
            "principles": design["principles"],
            "flow_diagram": design["flow_diagram"],
            "pacing_guide": design["pacing_guide"],
            "landmark_system": design["landmark_system"],
            "encounter_design": design["encounter_design"],
            "playtesting_checklist": design["playtesting_checklist"],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# MCP Tool Definitions
# ---------------------------------------------------------------------------

GAMEDEV_TOOLS = [
    {
        "name": "gamedev_design_analyze",
        "description": "Analyze a game concept for fun-factor, engagement, and profitability. Scores the concept and provides strengths, weaknesses, engagement loops, monetization fit, and similar games.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "Game concept description",
                },
                "genre": {
                    "type": "string",
                    "enum": [
                        "rpg",
                        "fps",
                        "puzzle",
                        "platformer",
                        "sim",
                        "strategy",
                        "horror",
                        "idle",
                        "roguelike",
                        "social",
                    ],
                    "description": "Game genre",
                },
                "platform": {
                    "type": "string",
                    "enum": ["pc", "mobile", "console", "vr", "roblox"],
                    "default": "pc",
                },
            },
            "required": ["concept", "genre"],
        },
    },
    {
        "name": "gamedev_scaffold_project",
        "description": "Generate a complete game project scaffold with real working code files for Unity, Unreal, Roblox, or Godot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "engine": {
                    "type": "string",
                    "enum": ["unity", "unreal", "roblox", "godot"],
                    "description": "Game engine",
                },
                "genre": {
                    "type": "string",
                    "description": "Game genre (e.g. fps, rpg, platformer)",
                },
                "name": {
                    "type": "string",
                    "default": "MyGame",
                    "description": "Project name",
                },
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional feature list",
                },
            },
            "required": ["engine", "genre"],
        },
    },
    {
        "name": "gamedev_mechanics_guide",
        "description": "Design game mechanics for a specific genre with complexity level. Returns core loop, mechanic systems, progression, and balance considerations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "genre": {
                    "type": "string",
                    "enum": [
                        "rpg",
                        "fps",
                        "puzzle",
                        "platformer",
                        "sim",
                        "strategy",
                        "horror",
                        "idle",
                        "roguelike",
                        "social",
                    ],
                    "description": "Game genre",
                },
                "complexity": {
                    "type": "string",
                    "enum": ["casual", "core", "hardcore"],
                    "default": "core",
                    "description": "Target complexity/depth level",
                },
            },
            "required": ["genre"],
        },
    },
    {
        "name": "gamedev_monetization",
        "description": "Recommend monetization strategies based on platform, genre, and audience. Includes ethical considerations and revenue estimates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["pc", "mobile", "console", "roblox"],
                    "default": "mobile",
                },
                "genre": {
                    "type": "string",
                    "enum": [
                        "rpg",
                        "fps",
                        "puzzle",
                        "platformer",
                        "sim",
                        "strategy",
                        "horror",
                        "idle",
                        "roguelike",
                        "social",
                    ],
                    "default": "puzzle",
                },
                "audience": {
                    "type": "string",
                    "enum": ["casual", "core", "hardcore"],
                    "default": "casual",
                },
            },
        },
    },
    {
        "name": "gamedev_optimization",
        "description": "Engine-specific optimization advice for performance issues like low FPS, draw calls, memory, load times, network lag, or build size.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "engine": {
                    "type": "string",
                    "enum": ["unity", "unreal", "roblox", "godot"],
                    "description": "Game engine",
                },
                "issue": {
                    "type": "string",
                    "enum": [
                        "low_fps",
                        "draw_calls",
                        "memory",
                        "load_times",
                        "network_lag",
                        "build_size",
                    ],
                    "description": "Performance issue to diagnose",
                },
            },
            "required": ["engine", "issue"],
        },
    },
    {
        "name": "gamedev_compare_engines",
        "description": "Compare Unity, Unreal, Godot, and Roblox engines for a specific project type, team size, and budget.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_type": {
                    "type": "string",
                    "enum": [
                        "2d",
                        "3d_open_world",
                        "fps",
                        "mobile",
                        "social",
                        "vr",
                        "general",
                    ],
                    "description": "Type of game project",
                },
                "team_size": {
                    "type": "string",
                    "enum": ["solo", "small", "medium", "large"],
                    "default": "small",
                },
                "budget": {
                    "type": "string",
                    "enum": ["none", "indie", "aa", "aaa"],
                    "default": "indie",
                },
            },
            "required": ["project_type"],
        },
    },
    {
        "name": "gamedev_level_design",
        "description": "Level design principles and patterns for specific level types (tutorial, boss fight, exploration, hub world, multiplayer map).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "genre": {
                    "type": "string",
                    "enum": [
                        "rpg",
                        "fps",
                        "puzzle",
                        "platformer",
                        "sim",
                        "strategy",
                        "horror",
                        "idle",
                        "roguelike",
                        "social",
                    ],
                    "description": "Game genre",
                },
                "level_type": {
                    "type": "string",
                    "enum": [
                        "tutorial",
                        "boss_fight",
                        "exploration",
                        "hub_world",
                        "multiplayer_map",
                    ],
                    "description": "Type of level to design",
                },
            },
            "required": ["genre", "level_type"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


def gamedev_handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch MCP tool call to the appropriate handler function."""
    dispatch = {
        "gamedev_design_analyze": lambda a: gamedev_design_analyze(
            a["concept"], a["genre"], a.get("platform", "pc")
        ),
        "gamedev_scaffold_project": lambda a: gamedev_scaffold_project(
            a["engine"], a["genre"], a.get("name", "MyGame"), a.get("features")
        ),
        "gamedev_mechanics_guide": lambda a: gamedev_mechanics_guide(
            a["genre"], a.get("complexity", "core")
        ),
        "gamedev_monetization": lambda a: gamedev_monetization(
            a.get("platform", "mobile"),
            a.get("genre", "puzzle"),
            a.get("audience", "casual"),
        ),
        "gamedev_optimization": lambda a: gamedev_optimization(a["engine"], a["issue"]),
        "gamedev_compare_engines": lambda a: gamedev_compare_engines(
            a["project_type"], a.get("team_size", "small"), a.get("budget", "indie")
        ),
        "gamedev_level_design": lambda a: gamedev_level_design(
            a["genre"], a["level_type"]
        ),
    }
    handler = dispatch.get(name)
    if handler:
        return handler(args)
    return {"status": "error", "error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# CLI entrypoint (for standalone testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python game-dev-module.py <tool_name> <json_args>")
        print("Available tools:", ", ".join(t["name"] for t in GAMEDEV_TOOLS))
        sys.exit(1)

    tool_name = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    result = gamedev_handle_tool_call(tool_name, args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
