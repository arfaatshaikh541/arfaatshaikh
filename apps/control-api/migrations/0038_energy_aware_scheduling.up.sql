-- Milestone 14: Energy-Aware Scheduling.
--
-- The approved architecture's entity list for this milestone (EnergyProfile,
-- CarbonIntensity, EnergyPreference, CarbonPreference, ScheduleWindow,
-- SustainabilityEvidence) is partially already built: capacity_offers'
-- estimated_kwh_per_unit_hour and placement_evaluations' estimated_energy_kwh
-- have existed since Milestone 5 and already act as EvaluatePlacement's
-- ranking tie-break (cost, then energy, then offer id) -- an "energy data
-- model" of sorts, just never named as one. There is no carbon-intensity or
-- renewable-mix data anywhere, and no per-tenant preference mechanism of any
-- kind exists in this codebase yet (Milestones 1-13 configure tenant-facing
-- behaviour only through budgets/SLOs/policies, never a plain preference
-- knob) -- both are genuinely new here.
--
-- Preferences are added directly as columns on enterprise_tenants, not a new
-- 1:1 preferences table, the same "1:1 facts about a single row are columns,
-- not their own table" reasoning Milestone 4's model_versions doc comment
-- already applied to hardware_requirements/retention_policy. A single
-- enum-like sustainability_ranking_mode column covers both "energy
-- preferences" and "cost and energy trade-offs" as one tenant-configurable
-- knob, rather than a pile of independent boolean weights that could
-- contradict each other; max_carbon_intensity_g_per_kwh is a separate, hard
-- ceiling (a preference with real teeth, not just a ranking nudge) -- this
-- milestone's actual "carbon preferences" requirement.
--
-- Schedule windows are added to placement_requests, not a new table: a
-- window is a property of one specific placement request, not an
-- independently-lifecycled entity. A new 'deferred' status value lets a
-- tenant tell "this request is deliberately waiting for its window" apart
-- from the pre-existing 'evaluated' (which already meant "no reservation
-- happened yet" for every other reason -- no eligible capacity, or a
-- simulate=true call). No scheduler/cron is introduced anywhere in this
-- migration or the module it backs -- consistent with every prior
-- milestone's documented absence of one, "non-urgent scheduling" is
-- evaluated lazily on each EvaluatePlacement call, the same lazy,
-- on-demand discipline reservation-expiry reclamation already established.
--
-- Sustainability evidence is added directly to placement_evaluations, not a
-- new table -- the exact same reasoning estimated_energy_kwh already
-- established for energy: a durable, per-candidate record of what was
-- actually resolved at evaluation time, not a separate audit trail.

ALTER TABLE enterprise_tenants
    ADD COLUMN sustainability_ranking_mode TEXT NOT NULL DEFAULT 'cost_first'
        CHECK (sustainability_ranking_mode IN ('cost_first', 'energy_first', 'carbon_first')),
    ADD COLUMN max_carbon_intensity_g_per_kwh NUMERIC(10,2)
        CHECK (max_carbon_intensity_g_per_kwh IS NULL OR max_carbon_intensity_g_per_kwh >= 0);

ALTER TABLE placement_requests
    ADD COLUMN non_urgent BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN schedule_window_start TIMESTAMPTZ,
    ADD COLUMN schedule_window_end TIMESTAMPTZ,
    ADD CONSTRAINT placement_requests_schedule_window_order
        CHECK (schedule_window_start IS NULL OR schedule_window_end IS NULL OR schedule_window_start < schedule_window_end);

ALTER TABLE placement_requests DROP CONSTRAINT placement_requests_status_check;
ALTER TABLE placement_requests ADD CONSTRAINT placement_requests_status_check
    CHECK (status IN ('evaluated', 'reserved', 'expired', 'cancelled', 'deferred'));

ALTER TABLE placement_evaluations
    ADD COLUMN carbon_intensity_g_per_kwh NUMERIC(10,2) NOT NULL DEFAULT 0,
    ADD COLUMN renewable_percentage NUMERIC(5,2) NOT NULL DEFAULT 0,
    ADD COLUMN estimated_carbon_kg NUMERIC(14,4) NOT NULL DEFAULT 0;
