from __future__ import annotations

from madspec_cli.memory import capture_stage_memory, checkpoint_stage_memory, retrieve_memory_context, validate_branch_memory
from madspec_cli.memory.stages.architecture.state import architecture_reference_errors


def test_architecture_stage_retrieve_returns_status_and_full_artifact(memory_project) -> None:
    paths = memory_project.paths
    memory_project.seed_concept_for_design()
    memory_project.write_design_prototypes()

    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        design_overview="A workspace-first web UI with focused transitions between booking, profile tuning, and exports.",
        platforms=["Web"],
        zones=[
            "operations::Operations::Daily scheduling workspace",
            "settings::Settings::Profile and export configuration",
        ],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/index.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::settings::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::settings::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=[
            "manage-booking::schedule-board::Create booking::Open booking details with reminders",
            "manage-booking::profile-studio::Review profile::Confirm public profile details",
            "manage-booking::export-hub::Export summary::Download account summary",
        ],
        navigation=[
            "schedule-board::profile-studio::Profile settings shortcut",
            "profile-studio::export-hub::Export settings CTA",
        ],
        screen_data=[
            "schedule-board::displayed::Upcoming bookings with reminder state",
            "schedule-board::input::Reminder lead time",
            "profile-studio::input::Public display name",
            "export-hub::displayed::Export download url",
        ],
        status="validated",
    )

    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.architecture",
        summary="Captured architecture iteration",
        architecture_overview="A modular web architecture centered on scheduling workflows and server-driven UI contracts.",
        project_structure="feature-first::Keep booking flows, profile tuning, and exports isolated by capability",
        directories=[
            "src/features/scheduling::Booking workflow handlers and orchestration",
            "src/features/profile::Profile editing logic",
            "src/features/exports::Export generation handlers",
        ],
        entities=[
            "Booking::Customer booking and reminder configuration",
            "Profile::Public profile settings",
            "ExportJob::Generated export package",
        ],
        entity_fields=[
            "Booking::id::uuid::required::Primary booking identifier",
            "Booking::reminder lead time::integer::required::Reminder lead time in minutes",
            "Profile::public display name::string::required::Display name shown to customers",
            "ExportJob::download url::string::required::Download location for generated export",
        ],
        entity_relationships=[
            "Booking::Profile::belongs-to::Bookings are owned by the freelancer profile",
        ],
        entity_states=["ExportJob::ready::Export package is ready for download"],
        endpoints=[
            "update-booking-reminder::PUT::/bookings/{id}/reminder::Update booking reminder configuration",
            "update-profile::PUT::/profile::Update freelancer profile settings",
            "download-export::GET::/exports/latest::Fetch the latest export package",
        ],
        endpoint_screens=[
            "update-booking-reminder::schedule-board",
            "update-profile::profile-studio",
            "download-export::export-hub",
        ],
        endpoint_fields=[
            "update-booking-reminder::path::id::uuid::required::Booking identifier",
            "update-booking-reminder::request::Reminder lead time::integer::required::Reminder lead time in minutes",
            "update-booking-reminder::response:200::Upcoming bookings with reminder state::array::required::Updated booking cards with reminder state",
            "update-profile::request::Public display name::string::required::Updated public display name",
            "update-profile::response:200::profile status::string::required::Profile save status",
            "download-export::response:200::Export download url::string::required::Download URL for latest export",
        ],
        endpoint_errors=["download-export::404::export_not_ready::Export package is not ready yet"],
        integrations=[
            "Email provider::external-api::Deliver reminders to customers::schedule-board|background worker",
        ],
        code_principles=[
            "Keep HTTP handlers thin and move workflow rules into feature services.",
        ],
        architecture_patterns=["Repository::Isolate persistence details from feature logic"],
        security_notes=[
            "Authorize profile and booking mutations against the current freelancer account.",
        ],
        performance_notes=[
            "Reuse precomputed export metadata to avoid rebuilding the package on every download request.",
        ],
        next_actions=["Proceed to mvp.plan"],
        status="validated",
    )
    retrieved = retrieve_memory_context(memory_project.project_path, "main", "mvp.architecture")

    assert captured["accepted"] is True
    assert retrieved["artifact_state"]["architecture"] is None
    assert retrieved["architecture_status"]["is_complete"] is True
    assert retrieved["architecture_status"]["counts"] == {
        "directories": 3,
        "entities": 3,
        "endpoints": 3,
        "integrations": 1,
        "code_principles": 1,
        "patterns": 1,
    }

    checkpointed = checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.architecture",
        "Architecture ratified for implementation planning",
        evidence=[
            ".madspec/main/architecture.md",
            ".madspec/main/data-model.md",
            ".madspec/main/contracts/openapi.yaml",
        ],
    )
    retrieved_full = retrieve_memory_context(
        memory_project.project_path,
        "main",
        "mvp.architecture",
        full_artifact=True,
        include_history=True,
    )

    assert checkpointed["accepted"] is True
    assert retrieved_full["artifact_state"]["architecture"]["checkpointSummary"] == "Architecture ratified for implementation planning"
    assert retrieved_full["artifact_state"]["architecture"]["revision"] == 1
    assert "A modular web architecture centered on scheduling workflows" in (paths["branch_dir"] / "architecture.md").read_text(encoding="utf-8")
    assert "Booking" in (paths["branch_dir"] / "data-model.md").read_text(encoding="utf-8")
    assert "update-booking-reminder" in (paths["branch_dir"] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert validate_branch_memory(memory_project.project_path, "main") == []


def test_capture_architecture_response_alias_satisfies_displayed_field_coverage(memory_project) -> None:
    memory_project.seed_concept_for_design()
    memory_project.write_design_prototypes()

    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        design_overview="A Telegram publishing workspace with editing and event monitoring.",
        platforms=["Web"],
        zones=[
            "settings::Settings::Bot setup and verification",
            "operations::Operations::Post editing and publish monitoring",
        ],
        screens=[
            "bot-connection::Bot connection::settings::.madspec/main/ui-prototype/index.html::Configure bot token and target channel",
            "workspace-main::Workspace main::operations::.madspec/main/ui-prototype/schedule-board.html::Edit and preview the current post",
            "publish-log::Publish log::operations::.madspec/main/ui-prototype/export-hub.html::Review publish attempts",
        ],
        screen_features=[
            "bot-connection::p1::Booking workflow",
            "workspace-main::p2::Profile studio",
            "publish-log::p3::Export hub",
        ],
        flows=["publish-post::Publish post::Prepare and send a post to Telegram"],
        flow_steps=[
            "publish-post::bot-connection::Verify bot::Confirm Telegram access works",
            "publish-post::workspace-main::Edit post::Prepare post content",
            "publish-post::publish-log::Review result::Inspect publish attempt history",
        ],
        screen_data=[
            "bot-connection::displayed::is_verified",
            "workspace-main::displayed::post-core",
            "publish-log::displayed::publish-events",
            "workspace-main::input::content_blocks",
        ],
        status="validated",
    )

    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.architecture",
        architecture_overview="Backend-first Telegram publishing architecture with feature-first modules.",
        project_structure="feature-first::Keep bot-connection, workspace, and publish-log isolated by capability",
        directories=[
            "src/features/bot-connection::Bot setup and verification logic",
            "src/features/workspace::Post editing and publishing logic",
            "src/features/publish-log::Publish attempt history",
        ],
        entities=[
            "Post::Draft or published content item",
            "PublishEvent::Attempt to publish a post",
        ],
        entity_fields=[
            "Post::id::uuid::required::Primary post identifier",
            "Post::content_blocks::json::required::Structured post content",
            "PublishEvent::id::uuid::required::Primary event identifier",
            "PublishEvent::status::string::required::Latest publish attempt status",
        ],
        endpoints=[
            "getBotConfig::GET::/api/bot-config::Load current bot settings",
            "getPost::GET::/api/posts/{post_id}::Load a post for editing",
            "listPublishEvents::GET::/api/publish-log::Load publish history",
        ],
        endpoint_screens=[
            "getBotConfig::bot-connection",
            "getPost::workspace-main",
            "listPublishEvents::publish-log",
        ],
        endpoint_fields=[
            "getBotConfig::response::is_verified::boolean::required::Bot API verification status",
            "getPost::path::post_id::uuid::required::Post identifier",
            "getPost::request::content_blocks::json::required::Structured post content",
            "getPost::response::post-core::object::required::Core post data for the editor and preview",
            "listPublishEvents::response::publish-events::array::required::Chronological list of publish attempts",
        ],
        code_principles=["Keep HTTP handlers thin and move Telegram rules into feature services."],
        status="validated",
    )
    retrieved = retrieve_memory_context(memory_project.project_path, "main", "mvp.architecture")

    assert captured["accepted"] is True
    assert retrieved["architecture_status"]["missing_required_fields"] == []
    assert retrieved["architecture_status"]["reference_errors"] == []
    assert retrieved["architecture_status"]["is_complete"] is True


def test_architecture_reference_errors_ignore_screen_data_labels_after_separator() -> None:
    polluted_design_state = {
        "schemaVersion": 1,
        "designOverview": "Polluted design state from an earlier session.",
        "createdAt": "2026-03-12T00:00:00Z",
        "ratifiedAt": None,
        "updatedAt": "2026-03-12T00:00:00Z",
        "revision": 0,
        "platforms": ["Web"],
        "zones": [],
        "screens": [
            {
                "id": "publish-log",
                "title": "Publish log",
                "zone": "operations",
                "purpose": "Inspect publish attempts",
                "prototype": ".madspec/main/ui-prototype/publish-log.html",
                "platforms": [],
                "covers": {"p1": [], "p2": [], "p3": ["Publish log"]},
                "data": {
                    "displayed": [
                        "publish-events::Хронологический список попыток публикации с временем, статусом и сообщением Bot API."
                    ],
                    "input": [],
                },
            }
        ],
        "flows": [],
        "navigation": [],
        "platformConstraints": [],
        "nextActions": [],
        "checkpointSummary": "",
    }
    architecture_state = {
        "architectureOverview": "Backend-first Telegram publishing architecture with feature-first modules.",
        "projectStructure": {
            "strategy": "feature-first",
            "rationale": "Keep publish-log isolated by capability",
            "directories": [{"path": "src/features/publish-log", "purpose": "Publish attempt history"}],
        },
        "dataModel": {
            "entities": [
                {
                    "name": "PublishEvent",
                    "description": "Attempt to publish a post",
                    "fields": [{"name": "status", "type": "string", "required": True, "description": "Attempt status"}],
                    "relationships": [],
                    "states": [],
                }
            ]
        },
        "contracts": {
            "apiStyle": "rest-openapi",
            "endpoints": [
                {
                    "operationId": "listpublishevents",
                    "method": "GET",
                    "path": "/api/publish-events",
                    "summary": "Load publish history",
                    "screenIds": ["publish-log"],
                    "fields": [
                        {
                            "section": "response:200",
                            "name": "publish-events",
                            "type": "array",
                            "required": True,
                            "description": "Chronological list of publish attempts",
                        }
                    ],
                    "errors": [],
                }
            ],
        },
        "codePrinciples": ["Keep handlers thin."],
        "patterns": [],
        "integrations": [],
        "securityNotes": [],
        "performanceNotes": [],
        "nextActions": [],
    }

    errors = architecture_reference_errors(architecture_state, design_state=polluted_design_state)

    assert errors == []


def test_architecture_reference_errors_match_unicode_field_names() -> None:
    design_state = {
        "schemaVersion": 1,
        "designOverview": "Unicode field names should match.",
        "createdAt": "2026-03-12T00:00:00Z",
        "ratifiedAt": None,
        "updatedAt": "2026-03-12T00:00:00Z",
        "revision": 0,
        "platforms": ["Web"],
        "zones": [],
        "screens": [
            {
                "id": "profile",
                "title": "Profile",
                "zone": "settings",
                "purpose": "Review current profile state",
                "prototype": ".madspec/main/ui-prototype/profile.html",
                "platforms": [],
                "covers": {"p1": [], "p2": ["Profile"], "p3": []},
                "data": {"displayed": ["статус-публикации"], "input": []},
            }
        ],
        "flows": [],
        "navigation": [],
        "platformConstraints": [],
        "nextActions": [],
        "checkpointSummary": "",
    }
    architecture_state = {
        "architectureOverview": "Unicode-safe contract matching.",
        "projectStructure": {
            "strategy": "feature-first",
            "rationale": "Keep profile isolated by capability",
            "directories": [{"path": "src/features/profile", "purpose": "Profile screens"}],
        },
        "dataModel": {
            "entities": [
                {
                    "name": "Profile",
                    "description": "Profile aggregate",
                    "fields": [{"name": "id", "type": "uuid", "required": True, "description": "Primary id"}],
                    "relationships": [],
                    "states": [],
                }
            ]
        },
        "contracts": {
            "apiStyle": "rest-openapi",
            "endpoints": [
                {
                    "operationId": "getprofile",
                    "method": "GET",
                    "path": "/api/profile",
                    "summary": "Load current profile",
                    "screenIds": ["profile"],
                    "fields": [
                        {
                            "section": "response:200",
                            "name": "статус публикации",
                            "type": "string",
                            "required": True,
                            "description": "Current publication status",
                        }
                    ],
                    "errors": [],
                }
            ],
        },
        "codePrinciples": ["Keep handlers thin."],
        "patterns": [],
        "integrations": [],
        "securityNotes": [],
        "performanceNotes": [],
        "nextActions": [],
    }

    errors = architecture_reference_errors(architecture_state, design_state=design_state)

    assert errors == []


def test_validate_detects_out_of_sync_generated_architecture_artifacts(memory_project) -> None:
    paths = memory_project.paths
    memory_project.seed_concept_for_design()
    memory_project.write_design_prototypes()

    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        design_overview="A workspace-first web UI with focused transitions between booking, profile tuning, and exports.",
        platforms=["Web"],
        zones=[
            "operations::Operations::Daily scheduling workspace",
            "settings::Settings::Profile and export configuration",
        ],
        screens=[
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/index.html::Shows upcoming bookings and reminder actions",
            "profile-studio::Profile studio::settings::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "export-hub::Export hub::settings::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
        ],
        screen_features=[
            "schedule-board::p1::Booking workflow",
            "profile-studio::p2::Profile studio",
            "export-hub::p3::Export hub",
        ],
        flows=["manage-booking::Manage booking::Create and review a booking flow from one workspace"],
        flow_steps=[
            "manage-booking::schedule-board::Create booking::Open booking details with reminders",
            "manage-booking::profile-studio::Review profile::Confirm public profile details",
            "manage-booking::export-hub::Export summary::Download account summary",
        ],
        navigation=[
            "schedule-board::profile-studio::Profile settings shortcut",
            "profile-studio::export-hub::Export settings CTA",
        ],
        screen_data=[
            "schedule-board::displayed::Upcoming bookings with reminder state",
            "schedule-board::input::Reminder lead time",
            "profile-studio::input::Public display name",
            "export-hub::displayed::Export download url",
        ],
        status="validated",
    )
    capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.architecture",
        architecture_overview="Architecture baseline.",
        project_structure="feature-first::Keep booking flows, profile tuning, and exports isolated by capability",
        directories=[
            "src/features/scheduling::Booking workflow handlers and orchestration",
            "src/features/profile::Profile editing logic",
            "src/features/exports::Export generation handlers",
        ],
        entities=[
            "Booking::Customer booking and reminder configuration",
            "Profile::Public profile settings",
            "ExportJob::Generated export package",
        ],
        entity_fields=[
            "Booking::id::uuid::required::Primary booking identifier",
            "Booking::reminder lead time::integer::required::Reminder lead time in minutes",
            "Profile::public display name::string::required::Display name shown to customers",
            "ExportJob::download url::string::required::Download location for generated export",
        ],
        endpoints=[
            "update-booking-reminder::PUT::/bookings/{id}/reminder::Update booking reminder configuration",
            "update-profile::PUT::/profile::Update freelancer profile settings",
            "download-export::GET::/exports/latest::Fetch the latest export package",
        ],
        endpoint_screens=[
            "update-booking-reminder::schedule-board",
            "update-profile::profile-studio",
            "download-export::export-hub",
        ],
        endpoint_fields=[
            "update-booking-reminder::path::id::uuid::required::Booking identifier",
            "update-booking-reminder::request::Reminder lead time::integer::required::Reminder lead time in minutes",
            "update-booking-reminder::response:200::Upcoming bookings with reminder state::array::required::Updated booking cards with reminder state",
            "update-profile::request::Public display name::string::required::Updated public display name",
            "update-profile::response:200::profile status::string::required::Profile save status",
            "download-export::response:200::Export download url::string::required::Download URL for latest export",
        ],
        code_principles=["Keep HTTP handlers thin and move workflow rules into feature services."],
        status="validated",
    )
    checkpoint_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.architecture",
        "Architecture version one",
        evidence=[
            ".madspec/main/architecture.md",
            ".madspec/main/data-model.md",
            ".madspec/main/contracts/openapi.yaml",
        ],
    )

    (paths["branch_dir"] / "architecture.md").write_text("# drift\n", encoding="utf-8")
    (paths["branch_dir"] / "data-model.md").write_text("# drift\n", encoding="utf-8")
    (paths["branch_dir"] / "contracts" / "openapi.yaml").write_text("openapi: drift\n", encoding="utf-8")

    errors = validate_branch_memory(memory_project.project_path, "main")

    assert "architecture.md is out of sync with memory/stages/mvp.architecture.json" in errors
    assert "data-model.md is out of sync with memory/stages/mvp.architecture.json" in errors
    assert "contracts/openapi.yaml is out of sync with memory/stages/mvp.architecture.json" in errors
