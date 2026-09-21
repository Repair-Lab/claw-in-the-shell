-- =============================================================================
-- Migration 66: Ghost Chat ↔ Ghost LLM Manager Live-Verknüpfung
-- =============================================================================
-- Ghost Chat bekommt Live-Synchronisierung mit dem Ghost LLM Manager:
--   - Event-Listener für dbai:ghost_swap + dbai:llm_model_change
--   - Modell-Tab zeigt Ghost-Status pro Rolle mit Inline-Swap
--   - Warnung wenn Rolle keinen aktiven Ghost hat + Quick-Swap-Buttons
--   - Auto-Refresh alle 30s
--   - Bidirektionale Events bei Modell-Aktivierung/Deaktivierung
-- =============================================================================

BEGIN;

-- 1) Changelog
INSERT INTO dbai_knowledge.changelog (
    version, change_type, title, description,
    affected_modules, affected_files, author
) VALUES (
    '66',
    'feature',
    'Ghost Chat ↔ Ghost LLM Manager Live-Verknüpfung',
    'Ghost Chat synchronisiert sich live mit Ghost LLM Manager: Event-Listener (dbai:ghost_swap + dbai:llm_model_change) für Auto-Refresh, Modell-Tab zeigt Ghost-Status pro Rolle mit Inline-Swap, Warnung bei Rolle ohne aktiven Ghost mit Quick-Swap-Buttons, Auto-Refresh alle 30s, bidirektionale Events bei Modell-Aktivierung/Deaktivierung im LLM Manager.',
    '{}'::uuid[],
    ARRAY[
        'frontend/src/components/apps/GhostChat.jsx',
        'frontend/src/components/apps/LLMManager.jsx'
    ],
    'system'
);

-- 2) System-Memory
INSERT INTO dbai_knowledge.system_memory (title, content, category, priority) VALUES
(
    'Ghost Chat ↔ Ghost LLM Manager Architektur',
    'Ghost Chat und Ghost LLM Manager kommunizieren bidirektional über CustomEvents auf window:
- dbai:ghost_swap → von App.jsx WebSocket oder direkt dispatcht; beide Apps hören darauf
- dbai:llm_model_change → von GhostLLMManager bei activate/deactivate; GhostChat hört darauf
- GhostChat kann Swaps direkt via api.swapGhost() + Event-Dispatch auslösen
- ask_ghost() im Backend nutzt active_ghosts.model_id, NICHT ghost_default_model Config
- Wenn Rolle keinen Ghost hat → Fehler + Inline-Swap-Buttons im Chat',
    'architecture',
    8
),
(
    'Ghost Chat — Modell-Flow',
    'Modell-Flow: (1) swapGhost(role, model) → INSERT/UPDATE in active_ghosts. (2) askGhost → DB-Funktion ask_ghost() sucht active_ghosts für Rolle, nutzt model_id. (3) ghost_default_model Config = nur UI-Persistenz. (4) ghost_compatibility = Fitness-Score pro Rolle/Modell.',
    'workflow',
    7
),
(
    'Event-System — Komponenten-Kommunikation',
    'Inter-Komponenten-Events über window.dispatchEvent(new CustomEvent(...)):
- dbai:ghost_swap — Ghost-Modell zugewiesen (App.jsx WebSocket + direct)
- dbai:llm_model_change — Modell aktiviert/deaktiviert (GhostLLMManager)
Events kommen über WebSocket oder werden direkt dispatcht.',
    'convention',
    6
);

COMMIT;
