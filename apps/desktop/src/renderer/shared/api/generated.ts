export type paths = {
    "/api/v1/proxy-panel/connections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Connections */
        get: operations["list_connections_api_v1_proxy_panel_connections_get"];
        put?: never;
        /** Create Connection */
        post: operations["create_connection_api_v1_proxy_panel_connections_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-panel/connections/{connection_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Connection */
        delete: operations["delete_connection_api_v1_proxy_panel_connections__connection_id__delete"];
        options?: never;
        head?: never;
        /** Update Connection */
        patch: operations["update_connection_api_v1_proxy_panel_connections__connection_id__patch"];
        trace?: never;
    };
    "/api/v1/proxy-panel/connections/{connection_id}/api-key": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Replace Api Key */
        put: operations["replace_api_key_api_v1_proxy_panel_connections__connection_id__api_key_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-panel/connections/{connection_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Connection */
        post: operations["verify_connection_api_v1_proxy_panel_connections__connection_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-panel/connections/{connection_id}/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sync Connection */
        post: operations["sync_connection_api_v1_proxy_panel_connections__connection_id__sync_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Proxies */
        get: operations["list_proxies_api_v1_proxies_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Proxy */
        get: operations["get_proxy_api_v1_proxies__projection_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Proxy */
        patch: operations["update_proxy_api_v1_proxies__projection_id__patch"];
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/references": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Proxy References */
        get: operations["proxy_references_api_v1_proxies__projection_id__references_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/probe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Check Proxy Health */
        post: operations["check_proxy_health_api_v1_proxies__projection_id__probe_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/ip-auth": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Unavailable Get Ip Auth */
        get: operations["unavailable_get_ip_auth_api_v1_proxies__projection_id__ip_auth_get"];
        /** Unavailable Set Ip Auth */
        put: operations["unavailable_set_ip_auth_api_v1_proxies__projection_id__ip_auth_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/credentials": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Credentials Metadata */
        get: operations["get_credentials_metadata_api_v1_proxies__projection_id__credentials_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/credentials/rotate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Unavailable Rotate Credentials */
        post: operations["unavailable_rotate_credentials_api_v1_proxies__projection_id__credentials_rotate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/usage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Unavailable Usage */
        get: operations["unavailable_usage_api_v1_proxies__projection_id__usage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-panel/connections/{connection_id}/account-summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Unavailable Account Summary */
        get: operations["unavailable_account_summary_api_v1_proxy_panel_connections__connection_id__account_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-groups": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Groups */
        get: operations["list_groups_api_v1_proxy_groups_get"];
        put?: never;
        /** Create Group */
        post: operations["create_group_api_v1_proxy_groups_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-groups/{group_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Group */
        get: operations["get_group_api_v1_proxy_groups__group_id__get"];
        /** Update Group */
        put: operations["update_group_api_v1_proxy_groups__group_id__put"];
        post?: never;
        /** Delete Group */
        delete: operations["delete_group_api_v1_proxy_groups__group_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-groups/{group_id}/references": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Group References */
        get: operations["group_references_api_v1_proxy_groups__group_id__references_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/remote-state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Remote State */
        get: operations["remote_state_api_v1_proxies__projection_id__remote_state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-panel/connections/{connection_id}/locations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Locations */
        get: operations["locations_api_v1_proxy_panel_connections__connection_id__locations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/rotation-schedule": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Schedule */
        get: operations["schedule_api_v1_proxies__projection_id__rotation_schedule_get"];
        /** Save Rotation */
        put: operations["save_rotation_api_v1_proxies__projection_id__rotation_schedule_put"];
        post?: never;
        /** Clear Rotation */
        delete: operations["clear_rotation_api_v1_proxies__projection_id__rotation_schedule_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/change-ip": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Change Ip */
        post: operations["change_ip_api_v1_proxies__projection_id__change_ip_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/relocate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Relocate */
        post: operations["relocate_api_v1_proxies__projection_id__relocate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxies/{projection_id}/operation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Latest Operation */
        get: operations["latest_operation_api_v1_proxies__projection_id__operation_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-operations/{operation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Operation */
        get: operations["get_operation_api_v1_proxy_operations__operation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-operations/{operation_id}/reconcile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reconcile Operation */
        post: operations["reconcile_operation_api_v1_proxy_operations__operation_id__reconcile_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-operations/{operation_id}/acknowledge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Acknowledge Unknown */
        post: operations["acknowledge_unknown_api_v1_proxy_operations__operation_id__acknowledge_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/profiles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Profiles */
        get: operations["list_profiles_api_v1_profiles_get"];
        put?: never;
        /** Create Profile */
        post: operations["create_profile_api_v1_profiles_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/profiles/environment-options": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Environment Options */
        get: operations["environment_options_api_v1_profiles_environment_options_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/profiles/test-browsers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Test Browsers */
        get: operations["list_test_browsers_api_v1_profiles_test_browsers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/profiles/{profile_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Profile */
        get: operations["get_profile_api_v1_profiles__profile_id__get"];
        /** Update Profile */
        put: operations["update_profile_api_v1_profiles__profile_id__put"];
        post?: never;
        /** Delete Profile */
        delete: operations["delete_profile_api_v1_profiles__profile_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/profiles/{profile_id}/duplicate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Duplicate Profile */
        post: operations["duplicate_profile_api_v1_profiles__profile_id__duplicate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/profiles/{profile_id}/regenerate-fingerprint": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Regenerate Fingerprint */
        post: operations["regenerate_fingerprint_api_v1_profiles__profile_id__regenerate_fingerprint_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/profiles/{profile_id}/test-browser": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Open Test Browser */
        post: operations["open_test_browser_api_v1_profiles__profile_id__test_browser_post"];
        /** Close Test Browser */
        delete: operations["close_test_browser_api_v1_profiles__profile_id__test_browser_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proxy-options": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Proxy Options */
        get: operations["list_proxy_options_api_v1_proxy_options_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Providers */
        get: operations["list_providers_api_v1_model_providers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-providers/connection-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["preview_api_v1_model_providers_connection_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-providers/connect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Connect */
        post: operations["connect_api_v1_model_providers_connect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-providers/{provider_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Provider */
        get: operations["get_provider_api_v1_model_providers__provider_id__get"];
        /** Update Metadata */
        put: operations["update_metadata_api_v1_model_providers__provider_id__put"];
        post?: never;
        /** Delete Provider */
        delete: operations["delete_provider_api_v1_model_providers__provider_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-providers/{provider_id}/test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Test Provider */
        post: operations["test_provider_api_v1_model_providers__provider_id__test_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-providers/{provider_id}/models/discover": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Discover */
        get: operations["discover_api_v1_model_providers__provider_id__models_discover_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-providers/{provider_id}/models/test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Test Model */
        post: operations["test_model_api_v1_model_providers__provider_id__models_test_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-providers/{provider_id}/connection": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Connection */
        put: operations["update_connection_api_v1_model_providers__provider_id__connection_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-providers/{provider_id}/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Model */
        post: operations["create_model_api_v1_model_providers__provider_id__models_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/models/{model_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Model */
        put: operations["update_model_api_v1_models__model_id__put"];
        post?: never;
        /** Delete Model */
        delete: operations["delete_model_api_v1_models__model_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/models/options": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Options */
        get: operations["options_api_v1_models_options_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Catalog */
        get: operations["get_catalog_api_v1_kernels_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/installed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Installed */
        get: operations["get_installed_api_v1_kernels_installed_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/check-update": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Check Update */
        post: operations["check_update_api_v1_kernels_check_update_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/license": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get License */
        get: operations["get_license_api_v1_kernels_license_get"];
        put?: never;
        /** Connect License */
        post: operations["connect_license_api_v1_kernels_license_post"];
        /** Disconnect License */
        delete: operations["disconnect_license_api_v1_kernels_license_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/default": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Default */
        get: operations["get_default_api_v1_kernels_default_get"];
        /** Set Default */
        put: operations["set_default_api_v1_kernels_default_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Download */
        post: operations["download_api_v1_kernels_download_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/operations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Operations */
        get: operations["get_operations_api_v1_kernels_operations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/operations/{operation_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel */
        post: operations["cancel_api_v1_kernels_operations__operation_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/{version}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove */
        delete: operations["remove_api_v1_kernels__version__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/runtime": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Runtime */
        get: operations["runtime_api_v1_settings_runtime_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Dashboard */
        get: operations["dashboard_api_v1_dashboard_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kernels/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Events */
        get: operations["events_api_v1_kernels_events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/workflows": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Workflows */
        get: operations["list_workflows_api_v1_workflows_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/workflows/{workflowId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Workflow */
        get: operations["get_workflow_api_v1_workflows__workflowId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Projects */
        get: operations["list_projects_api_v1_projects_get"];
        put?: never;
        /** Create Project */
        post: operations["create_project_api_v1_projects_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Project */
        get: operations["get_project_api_v1_projects__projectId__get"];
        put?: never;
        post?: never;
        /** Delete Project */
        delete: operations["delete_project_api_v1_projects__projectId__delete"];
        options?: never;
        head?: never;
        /** Patch Project */
        patch: operations["patch_project_api_v1_projects__projectId__patch"];
        trace?: never;
    };
    "/api/v1/projects/{projectId}/open": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Open Project */
        post: operations["open_project_api_v1_projects__projectId__open_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Overview */
        get: operations["overview_api_v1_projects__projectId__overview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/operations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Operations */
        get: operations["operations_api_v1_projects__projectId__operations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/operations/{operationId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Operation */
        get: operations["operation_api_v1_projects__projectId__operations__operationId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/operations/by-idempotency-key/{key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Operation By Key */
        get: operations["operation_by_key_api_v1_projects__projectId__operations_by_idempotency_key__key__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/workspace/operations/by-idempotency-key/{key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Workspace Operation */
        get: operations["workspace_operation_api_v1_workspace_operations_by_idempotency_key__key__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/lifecycle-impact": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lifecycle Impact */
        get: operations["lifecycle_impact_api_v1_projects__projectId__lifecycle_impact_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Archive Project */
        post: operations["archive_project_api_v1_projects__projectId__archive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Restore Project */
        post: operations["restore_project_api_v1_projects__projectId__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/statistics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Project Statistics */
        get: operations["project_statistics_api_v1_projects__projectId__statistics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/statistics/{resultSetId}/tasks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Statistics Tasks */
        get: operations["statistics_tasks_api_v1_projects__projectId__statistics__resultSetId__tasks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/automations/{automationId}/batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Batch */
        post: operations["start_batch_api_v1_projects__projectId__automations__automationId__batches_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/follow-up-batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Follow Up Batch */
        post: operations["follow_up_batch_api_v1_projects__projectId__tasks__taskId__follow_up_batches_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/automations/{automationId}/input-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Inputs */
        post: operations["preview_inputs_api_v1_projects__projectId__automations__automationId__input_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/batches/{batchId}/stop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Stop Batch */
        post: operations["stop_batch_api_v1_projects__projectId__batches__batchId__stop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/batches/{batchId}/force-stop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Force Stop Batch */
        post: operations["force_stop_batch_api_v1_projects__projectId__batches__batchId__force_stop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Batches */
        get: operations["list_batches_api_v1_projects__projectId__batches_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/batches/{batchId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Batch */
        get: operations["get_batch_api_v1_projects__projectId__batches__batchId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tasks */
        get: operations["list_tasks_api_v1_projects__projectId__tasks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Task */
        get: operations["get_task_api_v1_projects__projectId__tasks__taskId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/node-attempts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Node Attempts */
        get: operations["node_attempts_api_v1_projects__projectId__tasks__taskId__node_attempts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Logs */
        get: operations["logs_api_v1_projects__projectId__tasks__taskId__logs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/outputs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Outputs */
        get: operations["outputs_api_v1_projects__projectId__tasks__taskId__outputs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/artifacts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Artifacts */
        get: operations["artifacts_api_v1_projects__projectId__tasks__taskId__artifacts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/artifacts/{artifactId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Artifact */
        get: operations["artifact_api_v1_projects__projectId__tasks__taskId__artifacts__artifactId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/artifacts/{artifactId}/content": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Artifact Content */
        get: operations["artifact_content_api_v1_projects__projectId__tasks__taskId__artifacts__artifactId__content_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Events */
        get: operations["read_events_api_v1_projects__projectId__tasks__taskId__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/events/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stream Events */
        get: operations["stream_events_api_v1_projects__projectId__tasks__taskId__events_stream_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/automations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Automations */
        get: operations["list_automations_api_v1_projects__projectId__automations_get"];
        put?: never;
        /** Create Automation */
        post: operations["create_automation_api_v1_projects__projectId__automations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/automations/{automationId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Automation */
        get: operations["get_automation_api_v1_projects__projectId__automations__automationId__get"];
        /** Update Automation */
        put: operations["update_automation_api_v1_projects__projectId__automations__automationId__put"];
        post?: never;
        /** Delete Automation */
        delete: operations["delete_automation_api_v1_projects__projectId__automations__automationId__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/automations/{automationId}/impact": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Automation Impact */
        get: operations["automation_impact_api_v1_projects__projectId__automations__automationId__impact_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/automations/{automationId}/validation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Validate Automation */
        get: operations["validate_automation_api_v1_projects__projectId__automations__automationId__validation_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/records": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Records */
        get: operations["list_records_api_v1_projects__projectId__tables__tableId__records_get"];
        put?: never;
        /** Create */
        post: operations["create_api_v1_projects__projectId__tables__tableId__records_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/records/batch": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Batch */
        post: operations["create_batch_api_v1_projects__projectId__tables__tableId__records_batch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/records/{recordKey}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get */
        get: operations["get_api_v1_projects__projectId__tables__tableId__records__recordKey__get"];
        put?: never;
        post?: never;
        /** Delete Record */
        delete: operations["delete_record_api_v1_projects__projectId__tables__tableId__records__recordKey__delete"];
        options?: never;
        head?: never;
        /** Update */
        patch: operations["update_api_v1_projects__projectId__tables__tableId__records__recordKey__patch"];
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/records/{recordKey}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Status */
        put: operations["status_api_v1_projects__projectId__tables__tableId__records__recordKey__status_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tables */
        get: operations["list_tables_api_v1_projects__projectId__tables_get"];
        put?: never;
        /** Create Table */
        post: operations["create_table_api_v1_projects__projectId__tables_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Table */
        get: operations["get_table_api_v1_projects__projectId__tables__tableId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Table */
        patch: operations["update_table_api_v1_projects__projectId__tables__tableId__patch"];
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/fields": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Fields */
        get: operations["list_fields_api_v1_projects__projectId__tables__tableId__fields_get"];
        put?: never;
        /** Create Field */
        post: operations["create_field_api_v1_projects__projectId__tables__tableId__fields_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/statuses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Statuses */
        get: operations["list_statuses_api_v1_projects__projectId__tables__tableId__statuses_get"];
        put?: never;
        /** Create Status */
        post: operations["create_status_api_v1_projects__projectId__tables__tableId__statuses_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/statuses/usage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Status Usage */
        get: operations["status_usage_api_v1_projects__projectId__tables__tableId__statuses_usage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/statuses/{statusId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Status */
        delete: operations["delete_status_api_v1_projects__projectId__tables__tableId__statuses__statusId__delete"];
        options?: never;
        head?: never;
        /** Update Status */
        patch: operations["update_status_api_v1_projects__projectId__tables__tableId__statuses__statusId__patch"];
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/fields/{fieldId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Field */
        patch: operations["update_field_api_v1_projects__projectId__tables__tableId__fields__fieldId__patch"];
        trace?: never;
    };
    "/api/v1/projects/{projectId}/mutation-impact": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["preview_api_v1_projects__projectId__mutation_impact_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/schema/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["preview_api_v1_projects__projectId__tables__tableId__schema_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/schema": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Commit */
        post: operations["commit_api_v1_projects__projectId__tables__tableId__schema_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/record-status-batches/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["preview_api_v1_projects__projectId__tables__tableId__record_status_batches_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/record-status-batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start */
        post: operations["start_api_v1_projects__projectId__tables__tableId__record_status_batches_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/record-status-batches/{operationId}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel */
        post: operations["cancel_api_v1_projects__projectId__tables__tableId__record_status_batches__operationId__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/exports/xlsx": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Export */
        post: operations["export_api_v1_projects__projectId__tables__tableId__exports_xlsx_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/operations/{operationId}/reconcile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reconcile */
        post: operations["reconcile_api_v1_projects__projectId__operations__operationId__reconcile_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/table-imports/excel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create */
        post: operations["create_api_v1_projects__projectId__table_imports_excel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/imports/excel/impact": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Impact */
        post: operations["impact_api_v1_projects__projectId__tables__tableId__imports_excel_impact_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/imports/excel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Replace */
        post: operations["replace_api_v1_projects__projectId__tables__tableId__imports_excel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/table-imports/excel/inspect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Inspect */
        post: operations["inspect_api_v1_projects__projectId__table_imports_excel_inspect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Environments */
        get: operations["list_environments_api_v1_projects__projectId__environments_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environments/{environmentId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Environment */
        get: operations["get_environment_api_v1_projects__projectId__environments__environmentId__get"];
        put?: never;
        post?: never;
        /** Delete Environment */
        delete: operations["delete_environment_api_v1_projects__projectId__environments__environmentId__delete"];
        options?: never;
        head?: never;
        /** Patch Environment */
        patch: operations["patch_environment_api_v1_projects__projectId__environments__environmentId__patch"];
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environments/{environmentId}/impact": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Environment Impact */
        get: operations["environment_impact_api_v1_projects__projectId__environments__environmentId__impact_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environment-instances": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Instances */
        get: operations["list_instances_api_v1_projects__projectId__environment_instances_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environment-instances/{instanceId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Instance */
        get: operations["get_instance_api_v1_projects__projectId__environment_instances__instanceId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environment-instances/{instanceId}/open": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Open Instance */
        post: operations["open_instance_api_v1_projects__projectId__environment_instances__instanceId__open_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environment-saves": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Save Environment */
        post: operations["save_environment_api_v1_projects__projectId__environment_saves_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tasks/{taskId}/end": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** End Task */
        post: operations["end_task_api_v1_projects__projectId__tasks__taskId__end_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environments/{environmentId}/maintenance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Maintenance */
        post: operations["start_maintenance_api_v1_projects__projectId__environments__environmentId__maintenance_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environments/{environmentId}/maintenance/discard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Discard Maintenance */
        post: operations["discard_maintenance_api_v1_projects__projectId__environments__environmentId__maintenance_discard_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environment-operations/{operationId}/repair": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Repair End */
        post: operations["repair_end_api_v1_projects__projectId__environment_operations__operationId__repair_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/environment-operations/{operationId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Environment Operation */
        get: operations["get_environment_operation_api_v1_projects__projectId__environment_operations__operationId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/manual-items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Manual Items */
        get: operations["list_manual_items_api_v1_projects__projectId__manual_items_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/manual-items/{manualItemId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Manual Item */
        get: operations["get_manual_item_api_v1_projects__projectId__manual_items__manualItemId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/manual-items/{manualItemId}/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resume Manual Item */
        post: operations["resume_manual_item_api_v1_projects__projectId__manual_items__manualItemId__resume_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/manual-items/{manualItemId}/finish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Finish Manual Item */
        post: operations["finish_manual_item_api_v1_projects__projectId__manual_items__manualItemId__finish_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/sheets/connections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Connections */
        get: operations["list_connections_api_v1_projects__projectId__sheets_connections_get"];
        put?: never;
        /** Create Connection */
        post: operations["create_connection_api_v1_projects__projectId__sheets_connections_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/sheets/connections/{connectionId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Connection */
        delete: operations["delete_connection_api_v1_projects__projectId__sheets_connections__connectionId__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sheets/inspect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Inspect */
        post: operations["inspect_api_v1_projects__projectId__tables__tableId__sheets_inspect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sheets/binding": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Binding */
        get: operations["read_binding_api_v1_projects__projectId__tables__tableId__sheets_binding_get"];
        /** Put Binding */
        put: operations["put_binding_api_v1_projects__projectId__tables__tableId__sheets_binding_put"];
        post?: never;
        /** Delete Binding */
        delete: operations["delete_binding_api_v1_projects__projectId__tables__tableId__sheets_binding_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Sync State */
        get: operations["sync_state_api_v1_projects__projectId__tables__tableId__sync_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sync/pull": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Pull */
        post: operations["pull_api_v1_projects__projectId__tables__tableId__sync_pull_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sync/push": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Push */
        post: operations["push_api_v1_projects__projectId__tables__tableId__sync_push_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sync/pause": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Pause */
        post: operations["pause_api_v1_projects__projectId__tables__tableId__sync_pause_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sync/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resume */
        post: operations["resume_api_v1_projects__projectId__tables__tableId__sync_resume_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sync-operations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Operations */
        get: operations["list_operations_api_v1_projects__projectId__tables__tableId__sync_operations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sync-operations/{syncOperationId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Operation */
        get: operations["read_operation_api_v1_projects__projectId__tables__tableId__sync_operations__syncOperationId__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sync-operations/{syncOperationId}/reconcile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reconcile */
        post: operations["reconcile_api_v1_projects__projectId__tables__tableId__sync_operations__syncOperationId__reconcile_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{projectId}/tables/{tableId}/sync-operations/{syncOperationId}/abandon": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Abandon */
        post: operations["abandon_api_v1_projects__projectId__tables__tableId__sync_operations__syncOperationId__abandon_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflows/{workflow_id}/execute": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Execute Workflow */
        post: operations["execute_workflow_api_workflows__workflow_id__execute_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflows/{workflow_id}/stop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Stop Workflow */
        post: operations["stop_workflow_api_workflows__workflow_id__stop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflows": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Workflows */
        get: operations["list_workflows_api_workflows_get"];
        put?: never;
        /** Create Workflow */
        post: operations["create_workflow_api_workflows_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflows/data-latest/full": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Latest Data */
        get: operations["latest_data_api_workflows_data_latest_full_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflows/global-variables": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Global Variables */
        get: operations["global_variables_api_workflows_global_variables_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflows/{workflow_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Workflow */
        get: operations["get_workflow_api_workflows__workflow_id__get"];
        /** Update Workflow */
        put: operations["update_workflow_api_workflows__workflow_id__put"];
        post?: never;
        /** Delete Workflow */
        delete: operations["delete_workflow_api_workflows__workflow_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflow-runs/{run_id}/results": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Results */
        get: operations["get_results_api_workflow_runs__run_id__results_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflow-runs/{run_id}/results/{sequence}/value": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Result Value */
        get: operations["get_result_value_api_workflow_runs__run_id__results__sequence__value_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflow-runs/{run_id}/results/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export Results */
        get: operations["export_results_api_workflow_runs__run_id__results_export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflow-runs/{run_id}/artifacts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Artifacts */
        get: operations["list_artifacts_api_workflow_runs__run_id__artifacts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflow-runs/{run_id}/artifacts/{artifact_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Artifact */
        get: operations["get_artifact_api_workflow_runs__run_id__artifacts__artifact_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflow-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Runs */
        get: operations["list_runs_api_workflow_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflow-runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["get_run_api_workflow_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/workflow-runs/{run_id}/logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Logs */
        get: operations["get_logs_api_workflow_runs__run_id__logs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/events/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stream Events */
        get: operations["stream_events_api_events_stream_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/events/commands": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Command */
        post: operations["submit_command_api_events_commands_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/events/commands/{command_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Command */
        get: operations["get_command_api_events_commands__command_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/events/input-prompts/{request_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Input Prompt */
        get: operations["get_input_prompt_api_events_input_prompts__request_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/environment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Environment */
        get: operations["environment_api_v1_android_environment_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/devices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Devices */
        get: operations["devices_api_v1_android_devices_get"];
        put?: never;
        /** Create */
        post: operations["create_api_v1_android_devices_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/devices/{device_id}/operations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Operation */
        post: operations["operation_api_v1_android_devices__device_id__operations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/devices/{device_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Preview */
        get: operations["preview_api_v1_android_devices__device_id__preview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/devices/{device_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Device */
        get: operations["device_api_v1_android_devices__device_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Rename */
        patch: operations["rename_api_v1_android_devices__device_id__patch"];
        trace?: never;
    };
    "/api/v1/android/profiles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Profiles */
        get: operations["profiles_api_v1_android_profiles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/profiles/{identifier}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Save Profile */
        put: operations["save_profile_api_v1_android_profiles__identifier__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Batches */
        get: operations["batches_api_v1_android_batches_get"];
        put?: never;
        /** Batch */
        post: operations["batch_api_v1_android_batches_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/batches/{identifier}/actions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Batch Action */
        post: operations["batch_action_api_v1_android_batches__identifier__actions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/allocations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Allocations */
        get: operations["allocations_api_v1_android_allocations_get"];
        put?: never;
        /** Allocate */
        post: operations["allocate_api_v1_android_allocations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/allocations/{identifier}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Cancel Allocation */
        delete: operations["cancel_allocation_api_v1_android_allocations__identifier__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/devices/{identifier}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** History */
        get: operations["history_api_v1_android_devices__identifier__runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Session */
        post: operations["session_api_v1_android_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/sessions/{identifier}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Session */
        get: operations["read_session_api_v1_android_sessions__identifier__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/sessions/{identifier}/actions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Action */
        post: operations["action_api_v1_android_sessions__identifier__actions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/sessions/{identifier}/input": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Command */
        post: operations["command_api_v1_android_sessions__identifier__input_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/sessions/{identifier}/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stream */
        get: operations["stream_api_v1_android_sessions__identifier__stream_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/sessions/{identifier}/apps": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Apps */
        get: operations["apps_api_v1_android_sessions__identifier__apps_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/sessions/{identifier}/apps/launch": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Launch */
        post: operations["launch_api_v1_android_sessions__identifier__apps_launch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/android/sessions/{identifier}/apps/install": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Install */
        post: operations["install_api_v1_android_sessions__identifier__apps_install_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
};
export type webhooks = Record<string, never>;
export type components = {
    schemas: {
        /** AccountSummary */
        AccountSummary: {
            /** Balance */
            balance?: string | null;
            /** Currency */
            currency?: string | null;
            /** Fetched At */
            fetched_at?: string | null;
        };
        /** ActionResult */
        ActionResult: {
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "accepted" | "failed";
            /** Operation Id */
            operation_id?: string | null;
            /** Resource */
            resource?: unknown | null;
            error?: components["schemas"]["ApiError"] | null;
        };
        /** ActionResult[ConnectionView] */
        ActionResult_ConnectionView_: {
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "accepted" | "failed";
            /** Operation Id */
            operation_id?: string | null;
            resource?: components["schemas"]["ConnectionView"] | null;
            error?: components["schemas"]["ApiError"] | null;
        };
        /** ActionResult[CredentialView] */
        ActionResult_CredentialView_: {
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "accepted" | "failed";
            /** Operation Id */
            operation_id?: string | null;
            resource?: components["schemas"]["CredentialView"] | null;
            error?: components["schemas"]["ApiError"] | null;
        };
        /** ActionResult[HealthSnapshot] */
        ActionResult_HealthSnapshot_: {
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "accepted" | "failed";
            /** Operation Id */
            operation_id?: string | null;
            resource?: components["schemas"]["HealthSnapshot"] | null;
            error?: components["schemas"]["ApiError"] | null;
        };
        /** ActionResult[IpAllowlist] */
        ActionResult_IpAllowlist_: {
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "accepted" | "failed";
            /** Operation Id */
            operation_id?: string | null;
            resource?: components["schemas"]["IpAllowlist"] | null;
            error?: components["schemas"]["ApiError"] | null;
        };
        /** ActionResult[SyncSnapshot] */
        ActionResult_SyncSnapshot_: {
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "accepted" | "failed";
            /** Operation Id */
            operation_id?: string | null;
            resource?: components["schemas"]["SyncSnapshot"] | null;
            error?: components["schemas"]["ApiError"] | null;
        };
        /** ActivityItem */
        ActivityItem: {
            /** Activityid */
            activityId: string;
            /** Kind */
            kind: string;
            /** Resource */
            resource: components["schemas"]["ProjectResourceLocator"] | components["schemas"]["AutomationResourceLocator"] | components["schemas"]["BatchResourceLocator"] | components["schemas"]["TaskResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["FieldResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"] | components["schemas"]["SyncResourceLocator"] | components["schemas"]["EnvironmentResourceLocator"];
            /** Summary */
            summary: string;
            /**
             * Occurredat
             * Format: date-time
             */
            occurredAt: string;
        };
        /** AllocationCreate */
        AllocationCreate: {
            /**
             * Requestid
             * Format: uuid
             */
            requestId: string;
            /**
             * Workflowid
             * Format: uuid
             */
            workflowId: string;
            /**
             * Profileid
             * Format: uuid
             */
            profileId: string;
            /**
             * Mode
             * @enum {string}
             */
            mode: "specified" | "automatic" | "temporary";
            /** Deviceid */
            deviceId?: string | null;
            /** Values */
            values?: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** AllocationRead */
        AllocationRead: {
            /** Id */
            id: string;
            /** Createdat */
            createdAt: string;
            /** State */
            state: string;
            /** Workflowname */
            workflowName: string;
            /** Profilename */
            profileName: string;
            /** Deviceid */
            deviceId?: string | null;
            /** Devicename */
            deviceName?: string | null;
            /** Runid */
            runId?: string | null;
            /** Error */
            error?: string | null;
            request: components["schemas"]["AllocationCreate"];
        };
        /** AndroidCreate */
        AndroidCreate: {
            /** Name */
            name: string;
            /**
             * Deviceid
             * Format: uuid
             */
            deviceId: string;
            /** Imageid */
            imageId: string;
            /**
             * Width
             * @default 720
             */
            width: number;
            /**
             * Height
             * @default 1280
             */
            height: number;
            /**
             * Dpi
             * @default 320
             */
            dpi: number;
            /**
             * Cpu
             * @default 1
             */
            cpu: number;
            /**
             * Memorymb
             * @default 1536
             */
            memoryMb: number;
            /**
             * Start
             * @default true
             */
            start: boolean;
        };
        /** AndroidDeviceCommand */
        AndroidDeviceCommand: {
            /**
             * Requestid
             * Format: uuid
             */
            requestId: string;
            /**
             * Action
             * @enum {string}
             */
            action: "start" | "stop" | "restart" | "delete" | "recover";
            /**
             * Deletedata
             * @default false
             */
            deleteData: boolean;
        };
        /** AndroidDeviceRead */
        AndroidDeviceRead: {
            /** Deviceid */
            deviceId: string;
            /** Name */
            name: string;
            /** Runtimeid */
            runtimeId: string;
            /** Ownerrunid */
            ownerRunId: string | null;
            /** Control */
            control: string;
            /** Generation */
            generation: number;
            /** Width */
            width: number;
            /** Height */
            height: number;
            /** Imageid */
            imageId: string;
            /** Androidstatus */
            androidStatus: string;
            /** Lasterror */
            lastError: string | null;
            /**
             * Cpu
             * @default 1
             */
            cpu: number;
            /**
             * Memorymb
             * @default 1536
             */
            memoryMb: number;
            /**
             * Dpi
             * @default 320
             */
            dpi: number;
            /**
             * Androidversion
             * @default 13
             */
            androidVersion: string;
            /**
             * Architecture
             * @default arm64
             */
            architecture: string;
            /**
             * Dataretained
             * @default false
             */
            dataRetained: boolean;
            /**
             * Deleted
             * @default false
             */
            deleted: boolean;
            operation?: components["schemas"]["AndroidOperation"] | null;
            /** Profileid */
            profileId?: string | null;
            /**
             * Profilename
             * @default Android 13 标准 · ARM64
             */
            profileName: string;
            /**
             * Instancetype
             * @default persistent
             */
            instanceType: string;
            /**
             * Locale
             * @default zh-CN
             */
            locale: string;
            /**
             * Timezone
             * @default Asia/Shanghai
             */
            timezone: string;
        };
        /** AndroidEnvironment */
        AndroidEnvironment: {
            /** Available */
            available: boolean;
            /** Platformsupported */
            platformSupported: boolean;
            /** Runtimeid */
            runtimeId: string;
            /** Message */
            message: string;
            /** Images */
            images?: components["schemas"]["AndroidImage"][];
            /**
             * Cpucount
             * @default 0
             */
            cpuCount: number;
            /**
             * Memorymb
             * @default 0
             */
            memoryMb: number;
        };
        /** AndroidImage */
        AndroidImage: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Reference */
            reference: string;
        };
        /** AndroidOperation */
        AndroidOperation: {
            /** Id */
            id: string;
            /** Action */
            action: string;
            /** State */
            state: string;
            /** Stage */
            stage: string;
            /** Error */
            error: string | null;
            /**
             * Startedat
             * Format: date-time
             */
            startedAt: string;
            /** Finishedat */
            finishedAt: string | null;
        };
        /** AndroidRename */
        AndroidRename: {
            /** Name */
            name: string;
        };
        /** ApiError */
        ApiError: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Request Id */
            request_id: string;
            /** Field Errors */
            field_errors?: {
                [key: string]: unknown;
            };
            /** Retry After Seconds */
            retry_after_seconds?: number | null;
            /**
             * Outcome Unknown
             * @default false
             */
            outcome_unknown: boolean;
        };
        /** ApiKeyUpdate */
        ApiKeyUpdate: {
            /** Expected Revision */
            expected_revision: number;
            /**
             * Api Key
             * Format: password
             */
            api_key: string;
        };
        /** AppInfo */
        AppInfo: {
            /** Packages */
            packages: string[];
            /** Currentpackage */
            currentPackage: string | null;
            /** Shellroot */
            shellRoot: string;
            /** Applicationroot */
            applicationRoot: string;
        };
        /** AppLaunch */
        AppLaunch: {
            /** Generation */
            generation: number;
            /** Packagename */
            packageName: string;
        };
        /** ArchiveProjectRequest */
        ArchiveProjectRequest: {
            /** Impactrevision */
            impactRevision: number;
            /** Expectedmanagementrevision */
            expectedManagementRevision: number;
        };
        /** AttentionItem */
        AttentionItem: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "batch" | "task" | "manual" | "resource" | "sync" | "cleanup";
            /** Resource */
            resource: components["schemas"]["ProjectResourceLocator"] | components["schemas"]["AutomationResourceLocator"] | components["schemas"]["BatchResourceLocator"] | components["schemas"]["TaskResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["FieldResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"] | components["schemas"]["SyncResourceLocator"] | components["schemas"]["EnvironmentResourceLocator"];
            /**
             * Severity
             * @enum {string}
             */
            severity: "info" | "warning" | "error";
            /** Message */
            message: string;
            /**
             * Occurredat
             * Format: date-time
             */
            occurredAt: string;
        };
        /** AutomationDeleteRequest */
        AutomationDeleteRequest: {
            /** Impactrevision */
            impactRevision: number;
            /** Expectedmanagementrevision */
            expectedManagementRevision: number;
            /**
             * Workflowdisposition
             * @enum {string}
             */
            workflowDisposition: "unlink" | "deleteOwned";
        };
        /** AutomationImpactView */
        AutomationImpactView: {
            /** Impactrevision */
            impactRevision: number;
            /** Impacts */
            impacts: components["schemas"]["Impact"][];
            /** Blockers */
            blockers: components["schemas"]["Blocker"][];
        };
        /** AutomationPage */
        AutomationPage: {
            /** Items */
            items: components["schemas"]["AutomationView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** AutomationResourceLocator */
        AutomationResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "automation";
            /** Projectid */
            projectId: string;
            /** Automationid */
            automationId: string;
        };
        /** AutomationUpdate */
        AutomationUpdate: {
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Workflowid */
            workflowId: string;
            inputPlan: components["schemas"]["InputPlan"];
            /** Parameterschema */
            parameterSchema: components["schemas"]["ParameterDefinition"][];
            /** Environmentpolicy */
            environmentPolicy: components["schemas"]["NewFromProfile"] | components["schemas"]["FixedEnvironment"] | components["schemas"]["InputEnvironment"];
            runPolicy: components["schemas"]["RunPolicy"];
            /** Expectedmanagementrevision */
            expectedManagementRevision: number;
        };
        /** AutomationValidationIssue */
        AutomationValidationIssue: {
            /** Path */
            path: string[];
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Resource */
            resource?: {
                [key: string]: unknown;
            } | null;
        };
        /** AutomationValidationView */
        AutomationValidationView: {
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "draft" | "blocked" | "unavailable";
            /** Valid */
            valid: boolean;
            /** Runnable */
            runnable: boolean;
            /** Issues */
            issues: components["schemas"]["AutomationValidationIssue"][];
            /** Capabilityrequirements */
            capabilityRequirements: components["schemas"]["CapabilityRequirement"][];
            /**
             * Checkedat
             * Format: date-time
             */
            checkedAt: string;
        };
        /** AutomationView */
        AutomationView: {
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Workflowid */
            workflowId: string;
            inputPlan: components["schemas"]["InputPlan"];
            /** Parameterschema */
            parameterSchema: components["schemas"]["ParameterDefinition"][];
            /** Environmentpolicy */
            environmentPolicy: components["schemas"]["NewFromProfile"] | components["schemas"]["FixedEnvironment"] | components["schemas"]["InputEnvironment"];
            runPolicy: components["schemas"]["RunPolicy"];
            /** Automationid */
            automationId: string;
            /** Projectid */
            projectId: string;
            /** Managementrevision */
            managementRevision: number;
            /** Capabilityrequirements */
            capabilityRequirements?: components["schemas"]["CapabilityRequirement"][];
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** AutomationWrite */
        AutomationWrite: {
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Workflowid */
            workflowId: string;
            inputPlan: components["schemas"]["InputPlan"];
            /** Parameterschema */
            parameterSchema: components["schemas"]["ParameterDefinition"][];
            /** Environmentpolicy */
            environmentPolicy: components["schemas"]["NewFromProfile"] | components["schemas"]["FixedEnvironment"] | components["schemas"]["InputEnvironment"];
            runPolicy: components["schemas"]["RunPolicy"];
        };
        /** BatchAction */
        BatchAction: {
            /**
             * Action
             * @enum {string}
             */
            action: "cancel" | "retry";
        };
        /** BatchCreate */
        BatchCreate: {
            /** Name */
            name: string;
            /**
             * Batchid
             * Format: uuid
             */
            batchId: string;
            /**
             * Profileid
             * Format: uuid
             */
            profileId: string;
            /** Profilerevision */
            profileRevision: number;
            /**
             * Quantity
             * @default 3
             */
            quantity: number;
            /**
             * Instancetype
             * @default persistent
             * @enum {string}
             */
            instanceType: "persistent" | "temporary";
            /**
             * Start
             * @default true
             */
            start: boolean;
            /**
             * Width
             * @default 720
             */
            width: number;
            /**
             * Height
             * @default 1280
             */
            height: number;
            /**
             * Locale
             * @default zh-CN
             */
            locale: string;
            /**
             * Timezone
             * @default Asia/Shanghai
             */
            timezone: string;
        };
        /** BatchDetail */
        BatchDetail: {
            batch: components["schemas"]["BatchView"];
            /** Statuscounts */
            statusCounts: {
                [key: string]: number;
            };
            /** Taskcount */
            taskCount: number;
            /**
             * Reusedinputgroupcount
             * @default 0
             */
            reusedInputGroupCount: number;
            /**
             * Unchangedinputstreak
             * @default 0
             */
            unchangedInputStreak: number;
            stopOperation: components["schemas"]["ProjectRunOperationSnapshot"] | null;
            /** Forcestopallowed */
            forceStopAllowed: boolean;
            /** Forcestopavailableat */
            forceStopAvailableAt: string | null;
            /** Configurationsnapshot */
            configurationSnapshot: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** BatchItem */
        BatchItem: {
            /** Deviceid */
            deviceId: string;
            /** Name */
            name: string;
            /** State */
            state: string;
            /** Error */
            error?: string | null;
        };
        /** BatchPage */
        BatchPage: {
            /** Items */
            items: components["schemas"]["BatchView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** BatchRead */
        BatchRead: {
            /** Id */
            id: string;
            /** Createdat */
            createdAt: string;
            /** State */
            state: string;
            request: components["schemas"]["BatchCreate"];
            /** Items */
            items: components["schemas"]["BatchItem"][];
        };
        /** BatchResourceLocator */
        BatchResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "batch";
            /** Projectid */
            projectId: string;
            /** Batchid */
            batchId: string;
        };
        /** BatchStartRequest */
        BatchStartRequest: {
            /** Expectedautomationrevision */
            expectedAutomationRevision: number;
            /** Parameters */
            parameters: {
                [key: string]: string | number | boolean | null;
            };
            /** Maxtasks */
            maxTasks?: number | null;
            /** Concurrency */
            concurrency?: number | null;
            /** Environmentoverride */
            environmentOverride?: (components["schemas"]["NewFromProfile"] | components["schemas"]["FixedEnvironment"] | components["schemas"]["InputEnvironment"]) | null;
        };
        /** BatchStopRequest */
        BatchStopRequest: {
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
            /** Reason */
            reason: string;
        };
        /** BatchView */
        BatchView: {
            /** Batchid */
            batchId: string;
            /** Projectid */
            projectId: string;
            /** Automationid */
            automationId: string;
            /** Automationname */
            automationName?: string | null;
            /** Startoperationid */
            startOperationId: string;
            /** Status */
            status: string;
            /** Statusrevision */
            statusRevision: number;
            /** Managementrevision */
            managementRevision: number;
            /** Requestedcount */
            requestedCount: number | null;
            /** Createdtaskcount */
            createdTaskCount: number;
            /** Activetaskcount */
            activeTaskCount: number;
            /** Claimgatestate */
            claimGateState?: string | null;
            /** Selectionoutcome */
            selectionOutcome?: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Completedat */
            completedAt?: string | null;
        };
        /** Blocker */
        Blocker: {
            /** Code */
            code: string;
            /** Resource */
            resource: components["schemas"]["ProjectResourceLocator"] | components["schemas"]["AutomationResourceLocator"] | components["schemas"]["BatchResourceLocator"] | components["schemas"]["TaskResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["FieldResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"] | components["schemas"]["SyncResourceLocator"] | components["schemas"]["EnvironmentResourceLocator"];
            /** State */
            state: string;
            /** Message */
            message: string;
            /** Operationid */
            operationId?: string | null;
        };
        /** BrowserApiError */
        BrowserApiError: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Details */
            details?: {
                [key: string]: unknown;
            };
            /** Requestid */
            requestId: string;
        };
        /** BrowserErrorEnvelope */
        BrowserErrorEnvelope: {
            error: components["schemas"]["BrowserApiError"];
        };
        /** CancelRecordStatusesResult */
        CancelRecordStatusesResult: {
            /** Operationid */
            operationId: string;
            /**
             * Subsequentblocksclosed
             * @constant
             */
            subsequentBlocksClosed: true;
        };
        /** Capability */
        Capability: {
            /** Key */
            key: string;
            /** Available */
            available: boolean;
            /**
             * Evidence
             * @enum {string}
             */
            evidence: "confirmed-public" | "confirmed-authenticated-doc" | "fixture-verified" | "synthetic" | "unknown";
            /** Reason */
            reason?: string | null;
            /** Constraints */
            constraints?: {
                [key: string]: unknown;
            };
        };
        /** CapabilityRequirement */
        CapabilityRequirement: {
            /** Capability */
            capability: string;
            /** Required */
            required: boolean;
            /** Available */
            available: boolean;
            /** Reason */
            reason?: string | null;
        };
        /** CleanupSummaryView */
        CleanupSummaryView: {
            /**
             * Status
             * @enum {string}
             */
            status: "notRequired" | "pending" | "running" | "succeeded" | "failed" | "unknown";
            /** Operationid */
            operationId?: string | null;
            /** Message */
            message?: string | null;
        };
        /** ColumnExcelIdentity */
        ColumnExcelIdentity: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "column";
            /** Columnindex */
            columnIndex: number;
        };
        /** CommittedStatusRevision */
        CommittedStatusRevision: {
            recordRef: components["schemas"]["DataRecordRef"];
            /** Statusrevision */
            statusRevision: number;
        };
        /** ConnectionCreate */
        ConnectionCreate: {
            /** Name */
            name: string;
            /**
             * Api Key
             * Format: password
             */
            api_key: string;
        };
        /** ConnectionList */
        ConnectionList: {
            /** Items */
            items: components["schemas"]["ConnectionView"][];
        };
        /** ConnectionUpdate */
        ConnectionUpdate: {
            /** Expected Revision */
            expected_revision: number;
            /** Name */
            name?: string | null;
        };
        /** ConnectionView */
        ConnectionView: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Has Secret */
            has_secret: boolean;
            /**
             * Status
             * @enum {string}
             */
            status: "unconfigured" | "verifying" | "connected" | "failed";
            /** Revision */
            revision: number;
            /** Last Verified At */
            last_verified_at?: string | null;
            /** Last Synced At */
            last_synced_at?: string | null;
            last_error?: components["schemas"]["ApiError"] | null;
            /** Capabilities */
            capabilities?: components["schemas"]["Capability"][];
        };
        /** ControlCommand */
        ControlCommand: {
            /** Generation */
            generation: number;
            /** Sequence */
            sequence: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "key" | "touch" | "text" | "rotate" | "release";
            /**
             * Action
             * @default 0
             */
            action: number;
            /**
             * Keycode
             * @default 0
             */
            keycode: number;
            /**
             * X
             * @default 0
             */
            x: number;
            /**
             * Y
             * @default 0
             */
            y: number;
            /**
             * Width
             * @default 720
             */
            width: number;
            /**
             * Height
             * @default 1280
             */
            height: number;
            /**
             * Text
             * @default
             */
            text: string;
        };
        /** CredentialView */
        CredentialView: {
            /** Credential Available */
            credential_available: boolean;
            /** Username */
            username?: string | null;
            /** Can Copy */
            can_copy: boolean;
            /** Can Rotate */
            can_rotate: boolean;
        };
        /** DashboardRead */
        DashboardRead: {
            /** Profiles */
            profiles: number;
            /** Enabledproxies */
            enabledProxies: number;
            /** Proxygroups */
            proxyGroups: number;
            /** Installedkernels */
            installedKernels: number;
            /** Modelproviders */
            modelProviders: number | null;
            /** Models */
            models: number | null;
            /**
             * Generatedat
             * Format: date-time
             */
            generatedAt: string;
        };
        /** DataCellView */
        DataCellView: {
            /** Fieldid */
            fieldId: string;
            /** Value */
            value: string | number | boolean | components["schemas"]["DataDateScalar"] | null;
            /**
             * Source
             * @enum {string}
             */
            source: "local" | "remote" | "formula";
            /** Readable */
            readable: boolean;
            /** Error */
            error?: string;
        };
        /** DataCellWrite */
        DataCellWrite: {
            /** Fieldid */
            fieldId: string;
            /** Value */
            value: string | number | boolean | components["schemas"]["DataDateScalar"] | null;
        };
        /** DataChanges */
        DataChanges: {
            /** Timezone */
            timezone: string;
            /**
             * Daystart
             * Format: date-time
             */
            dayStart: string;
            /** Newrecords */
            newRecords: number;
            /** Updatedrecords */
            updatedRecords: number;
        };
        /** DataDateScalar */
        DataDateScalar: {
            /**
             * Kind
             * @constant
             */
            kind: "date";
            /**
             * Precision
             * @enum {string}
             */
            precision: "date" | "datetime";
            /** Value */
            value: string;
            /** Offset */
            offset: string | null;
        };
        /** DataFieldCreate */
        DataFieldCreate: {
            definition: components["schemas"]["DataFieldWrite"];
            /** Expectedtablerevision */
            expectedTableRevision: number;
            /** Existingrecorddefault */
            existingRecordDefault?: string | number | boolean | components["schemas"]["DataDateScalar"] | null;
            /**
             * Sourcecolumnpolicy
             * @enum {string}
             */
            sourceColumnPolicy: "localOnly" | "mapped";
        };
        /** DataFieldDirectory */
        DataFieldDirectory: {
            /** Items */
            items: components["schemas"]["DataFieldView"][];
            /** Tablerevision */
            tableRevision: number;
        };
        /** DataFieldMutationView */
        DataFieldMutationView: {
            field: components["schemas"]["DataFieldView"];
            /** Tablerevision */
            tableRevision: number;
        };
        /** DataFieldPatch */
        DataFieldPatch: {
            definition: components["schemas"]["DataFieldWrite"];
            /** Expectedtablerevision */
            expectedTableRevision: number;
            /** Expectedfieldrevision */
            expectedFieldRevision: number;
            /** Impactrevision */
            impactRevision: number;
        };
        /** DataFieldRef */
        DataFieldRef: {
            /** Projectid */
            projectId: string;
            /** Tableid */
            tableId: string;
            /** Datasetgeneration */
            datasetGeneration: string;
            /** Fieldid */
            fieldId: string;
        };
        /** DataFieldView */
        DataFieldView: {
            /** Key */
            key: string;
            /** Name */
            name: string;
            /**
             * Type
             * @enum {string}
             */
            type: "string" | "number" | "boolean" | "date";
            /** Required */
            required: boolean;
            /** Validation */
            validation: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            ref: components["schemas"]["DataFieldRef"];
            /** Writable */
            writable: boolean;
            /** Formula */
            formula: boolean;
            /** Fieldrevision */
            fieldRevision: number;
        };
        /** DataFieldWrite */
        DataFieldWrite: {
            /** Key */
            key: string;
            /** Name */
            name: string;
            /**
             * Type
             * @enum {string}
             */
            type: "string" | "number" | "boolean" | "date";
            /** Required */
            required: boolean;
            /** Validation */
            validation: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** DataMutationBlocker */
        DataMutationBlocker: {
            /** Code */
            code: string;
            /** Resource */
            resource: components["schemas"]["FieldResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"];
            /** State */
            state: string;
            /** Message */
            message: string;
        };
        /** DataMutationImpact */
        DataMutationImpact: {
            /** Code */
            code: string;
            /** Resource */
            resource: components["schemas"]["FieldResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"];
            /** Message */
            message: string;
            /** Blocking */
            blocking: boolean;
        };
        /** DataRecordBatchCreate */
        DataRecordBatchCreate: {
            /** Datasetgeneration */
            datasetGeneration: string;
            /** Expectedtablerevision */
            expectedTableRevision: number;
            /** Rows */
            rows: components["schemas"]["DataRecordBatchRow"][];
        };
        /** DataRecordBatchItem */
        DataRecordBatchItem: {
            /** Clientrowid */
            clientRowId: string;
            record: components["schemas"]["DataRecordView"];
        };
        /** DataRecordBatchResponse */
        DataRecordBatchResponse: {
            /** Records */
            records: components["schemas"]["DataRecordBatchItem"][];
            operation: components["schemas"]["ProjectOperationView"];
        };
        /** DataRecordBatchResult */
        DataRecordBatchResult: {
            /** Records */
            records: components["schemas"]["DataRecordBatchItem"][];
        };
        /** DataRecordBatchRow */
        DataRecordBatchRow: {
            /** Clientrowid */
            clientRowId: string;
            /** Values */
            values: components["schemas"]["DataCellWrite"][];
        };
        /** DataRecordCreate */
        DataRecordCreate: {
            /** Datasetgeneration */
            datasetGeneration: string;
            /** Values */
            values: components["schemas"]["DataCellWrite"][];
        };
        /** DataRecordKey */
        DataRecordKey: {
            /**
             * Type
             * @enum {string}
             */
            type: "text" | "integer" | "uuid";
            /** Value */
            value: string;
        };
        /** DataRecordPage */
        DataRecordPage: {
            /** Items */
            items: components["schemas"]["DataRecordView"][];
            /** Total */
            total: number;
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Sort */
            sort: string;
        };
        /** DataRecordPatch */
        DataRecordPatch: {
            /** Datasetgeneration */
            datasetGeneration: string;
            /** Values */
            values: components["schemas"]["DataCellWrite"][];
            /**
             * Recordkeytype
             * @enum {string}
             */
            recordKeyType: "text" | "integer" | "uuid";
            /** Expectedcontentrevision */
            expectedContentRevision: number;
        };
        /** DataRecordRef */
        DataRecordRef: {
            /** Projectid */
            projectId: string;
            /** Tableid */
            tableId: string;
            /** Datasetgeneration */
            datasetGeneration: string;
            recordKey: components["schemas"]["DataRecordKey"];
        };
        /** DataRecordSlot */
        DataRecordSlot: {
            /** Slotid */
            slotId: string;
            target: components["schemas"]["DataRecordRef"] | null;
        };
        /** DataRecordStatusWrite */
        DataRecordStatusWrite: {
            /** Datasetgeneration */
            datasetGeneration: string;
            /**
             * Recordkeytype
             * @enum {string}
             */
            recordKeyType: "text" | "integer" | "uuid";
            /** Statusid */
            statusId: string | null;
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
            /** Expectedfromstatusid */
            expectedFromStatusId?: string | null;
        };
        /** DataRecordView */
        DataRecordView: {
            ref: components["schemas"]["DataRecordRef"];
            /** Values */
            values: components["schemas"]["DataCellView"][];
            /** Recordslots */
            recordSlots: components["schemas"]["DataRecordSlot"][];
            /** Statusid */
            statusId: string | null;
            /** Currentenvironmentid */
            currentEnvironmentId: string | null;
            /** Contentrevision */
            contentRevision: number;
            /** Statusrevision */
            statusRevision: number;
            /** Linkrevision */
            linkRevision: number;
            /** Deleted */
            deleted: boolean;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** DataSchemaCandidate */
        DataSchemaCandidate: {
            /** Datasetgeneration */
            datasetGeneration: string;
            /** Expectedtablerevision */
            expectedTableRevision: number;
            /** Fields */
            fields: (components["schemas"]["DataSchemaExisting"] | components["schemas"]["DataSchemaNew"])[];
        };
        /** DataSchemaCommit */
        DataSchemaCommit: {
            candidate: components["schemas"]["DataSchemaCandidate"];
            /** Impactrevision */
            impactRevision: number;
        };
        /** DataSchemaExisting */
        DataSchemaExisting: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "existing";
            /** Fieldid */
            fieldId: string;
            /** Expectedfieldrevision */
            expectedFieldRevision: number;
            definition: components["schemas"]["DataFieldWrite"];
        };
        /** DataSchemaImpact */
        DataSchemaImpact: {
            /** Impactrevision */
            impactRevision: number;
            /** Calculatedat */
            calculatedAt: string;
            /** Expiresat */
            expiresAt: string;
            /** Affectedrecords */
            affectedRecords: number;
            /** Backfillbytes */
            backfillBytes: number;
            /** Blockers */
            blockers: components["schemas"]["DataSchemaIssue"][];
            /** Warnings */
            warnings: components["schemas"]["DataSchemaIssue"][];
            referenceAvailability: components["schemas"]["DataSchemaReferenceAvailability"];
        };
        /** DataSchemaIssue */
        DataSchemaIssue: {
            /** Code */
            code: string;
            /** Fieldid */
            fieldId: string | null;
            /** Clientid */
            clientId: string | null;
            /** Message */
            message: string;
            /** Affectedrecords */
            affectedRecords: number | null;
            /** Taskid */
            taskId?: string | null;
            /** Runid */
            runId?: string | null;
            /** Referencesources */
            referenceSources?: string[];
        };
        /** DataSchemaNew */
        DataSchemaNew: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "new";
            /** Clientid */
            clientId: string;
            definition: components["schemas"]["DataFieldWrite"];
            /**
             * Sourcecolumnpolicy
             * @constant
             */
            sourceColumnPolicy: "localOnly";
            /** Existingrecorddefault */
            existingRecordDefault?: string | number | boolean | components["schemas"]["DataDateScalar"] | null;
        };
        /** DataSchemaReferenceAvailability */
        DataSchemaReferenceAvailability: {
            /**
             * Automations
             * @constant
             */
            automations: "notImplemented";
            /**
             * Sync
             * @constant
             */
            sync: "notImplemented";
        };
        /** DataSchemaResult */
        DataSchemaResult: {
            /**
             * Action
             * @constant
             */
            action: "saveSchema";
            /** Datasetgeneration */
            datasetGeneration: string;
            /** Tablerevision */
            tableRevision: number;
            /** Fields */
            fields: components["schemas"]["DataFieldView"][];
            /** Createdfieldids */
            createdFieldIds: {
                [key: string]: string;
            };
            /** Backfilledrecords */
            backfilledRecords: number;
        };
        /** DataStatusConfigurationReferences */
        DataStatusConfigurationReferences: {
            /**
             * Availability
             * @constant
             */
            availability: "notImplemented";
        };
        /** DataStatusCreate */
        DataStatusCreate: {
            /** Name */
            name: string;
            /** Color */
            color: string;
            /** Order */
            order: number;
            /** Expectedtablerevision */
            expectedTableRevision: number;
        };
        /** DataStatusDirectory */
        DataStatusDirectory: {
            /** Items */
            items: components["schemas"]["DataStatusView"][];
            /** Tablerevision */
            tableRevision: number;
        };
        /** DataStatusPatch */
        DataStatusPatch: {
            /** Name */
            name?: string;
            /** Color */
            color?: string;
            /** Order */
            order?: number;
            /** Expectedtablerevision */
            expectedTableRevision: number;
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
        };
        /** DataStatusUsage */
        DataStatusUsage: {
            /** Statusid */
            statusId: string;
            /** Currentrecords */
            currentRecords: number;
            /** Activebatchoperations */
            activeBatchOperations: number;
        };
        /** DataStatusUsageDirectory */
        DataStatusUsageDirectory: {
            /** Datasetgeneration */
            datasetGeneration: string;
            /** Calculatedat */
            calculatedAt: string;
            /** Items */
            items: components["schemas"]["DataStatusUsage"][];
            configurationReferences: components["schemas"]["DataStatusConfigurationReferences"];
        };
        /** DataStatusView */
        DataStatusView: {
            /** Statusid */
            statusId: string;
            /** Name */
            name: string;
            /** Color */
            color: string;
            /** Order */
            order: number;
            /** Statusrevision */
            statusRevision: number;
        };
        /** DataTableCreate */
        DataTableCreate: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Sourcekind
             * @default local
             * @constant
             */
            sourceKind: "local";
        };
        /** DataTablePage */
        DataTablePage: {
            /** Items */
            items: components["schemas"]["DataTableView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** DataTablePatch */
        DataTablePatch: {
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            /** Expectedtablerevision */
            expectedTableRevision: number;
        };
        /** DataTableSource */
        DataTableSource: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "local" | "excel" | "sheets" | "unconfigured";
            /** Filename */
            filename?: string | null;
            /** Sheetname */
            sheetName?: string | null;
            /** Importedat */
            importedAt?: string | null;
        };
        /** DataTableView */
        DataTableView: {
            /** Projectid */
            projectId: string;
            /** Tableid */
            tableId: string;
            /** Name */
            name: string;
            /** Description */
            description: string;
            /**
             * Sourcekind
             * @enum {string}
             */
            sourceKind: "local" | "excel" | "sheets" | "unconfigured";
            source?: components["schemas"]["DataTableSource"] | null;
            /** Datasetgeneration */
            datasetGeneration: string;
            /** Tablerevision */
            tableRevision: number;
            /** Identity */
            identity: components["schemas"]["SystemTableIdentity"] | components["schemas"]["FieldTableIdentity"];
            /** Slotdefinitions */
            slotDefinitions: components["schemas"]["TableSlotDefinition"][];
            /** Recordcount */
            recordCount: number;
            syncSummary: components["schemas"]["TableSyncSummary"];
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** DefaultKernelRead */
        DefaultKernelRead: {
            /** Revision */
            revision: number;
            kernel: components["schemas"]["KernelRefRead"] | null;
        };
        /** DefaultKernelWrite */
        DefaultKernelWrite: {
            /** Expectedrevision */
            expectedRevision: number;
            kernel: components["schemas"]["KernelRefRead"] | null;
        };
        /** DeleteProjectRequest */
        DeleteProjectRequest: {
            /** Confirmationname */
            confirmationName: string;
            /** Impactrevision */
            impactRevision: number;
            /** Expectedmanagementrevision */
            expectedManagementRevision: number;
        };
        /** DeletedResourceResult */
        DeletedResourceResult: {
            /** Target */
            target: components["schemas"]["ProjectResourceLocator"] | components["schemas"]["AutomationResourceLocator"] | components["schemas"]["BatchResourceLocator"] | components["schemas"]["TaskResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["FieldResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"] | components["schemas"]["SyncResourceLocator"] | components["schemas"]["EnvironmentResourceLocator"];
            /**
             * Deleted
             * @constant
             */
            deleted: true;
            /** Workflowid */
            workflowId?: string | null;
            /** Workflowdisposition */
            workflowDisposition?: ("unlink" | "deleteOwned") | null;
        };
        /** DeletionImpactReport */
        DeletionImpactReport: {
            /** Impactrevision */
            impactRevision: number;
            /** Target */
            target: components["schemas"]["StatusResourceLocator"] | components["schemas"]["RecordResourceLocator"];
            /** Changedigest */
            changeDigest: string;
            /** Expectedrevisions */
            expectedRevisions: {
                [key: string]: number;
            };
            /** Impacts */
            impacts: components["schemas"]["DataMutationImpact"][];
            /** Blockers */
            blockers: components["schemas"]["DataMutationBlocker"][];
            /**
             * Calculatedat
             * Format: date-time
             */
            calculatedAt: string;
        };
        /** DeviceRunRead */
        DeviceRunRead: {
            /** Runid */
            runId: string;
            /** Workflowname */
            workflowName: string;
            /** State */
            state: string;
            /** Currentnodeid */
            currentNodeId?: string | null;
            /**
             * Currentstep
             * @default 0
             */
            currentStep: number;
            /**
             * Totalsteps
             * @default 0
             */
            totalSteps: number;
            /** Steps */
            steps: {
                [key: string]: components["schemas"]["JsonValue"];
            }[];
            /** Handoff */
            handoff?: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
            /** Startedat */
            startedAt: string;
        };
        /** EmptyCommand */
        EmptyCommand: Record<string, never>;
        /** Endpoint */
        Endpoint: {
            /** Host */
            host: string;
            /** Port */
            port: number;
        };
        /** EnvironmentDeleteRequest */
        EnvironmentDeleteRequest: {
            /** Impactrevision */
            impactRevision: number;
            /** Expectedmetadatarevision */
            expectedMetadataRevision: number;
            /** Expectedcontentgeneration */
            expectedContentGeneration: number;
        };
        /** EnvironmentDetailView */
        EnvironmentDetailView: {
            environment: components["schemas"]["EnvironmentView"];
            activeInstance: components["schemas"]["EnvironmentInstanceView"] | null;
            /**
             * Linkedrecordcount
             * @default 0
             */
            linkedRecordCount: number;
        };
        /** EnvironmentEndRequest */
        EnvironmentEndRequest: {
            /** Taskid */
            taskId: string;
            /** Runid */
            runId: string;
            /** Instanceid */
            instanceId: string;
            /** Expectedusegeneration */
            expectedUseGeneration: number;
            /** Executiongeneration */
            executionGeneration: number;
            /** Retainenvironment */
            retainEnvironment: {
                [key: string]: unknown;
            };
        };
        /** EnvironmentImpactView */
        EnvironmentImpactView: {
            /** Impactrevision */
            impactRevision: number;
            /** Impacts */
            impacts: {
                [key: string]: unknown;
            }[];
            /** Blockers */
            blockers: {
                [key: string]: unknown;
            }[];
        };
        /** EnvironmentInstancePage */
        EnvironmentInstancePage: {
            /** Items */
            items: components["schemas"]["EnvironmentInstanceView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** EnvironmentInstanceView */
        EnvironmentInstanceView: {
            /** Instanceid */
            instanceId: string;
            /** Projectid */
            projectId: string;
            /** Environmentid */
            environmentId: string | null;
            /** State */
            state: string;
            /** Source */
            source: string;
            /** Sourcecontentgeneration */
            sourceContentGeneration: number | null;
            /** Instanceusegeneration */
            instanceUseGeneration: number;
            /** Activetaskid */
            activeTaskId: string | null;
            /** Activerunid */
            activeRunId: string | null;
            /** Maintenanceoperationid */
            maintenanceOperationId: string | null;
            /** Profileid */
            profileId: string;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** EnvironmentOpenRequest */
        EnvironmentOpenRequest: {
            /** Expectedusegeneration */
            expectedUseGeneration: number;
        };
        /** EnvironmentOperationSnapshot */
        EnvironmentOperationSnapshot: {
            /** Operationid */
            operationId: string;
            /** Projectid */
            projectId: string | null;
            /** Idempotencykey */
            idempotencyKey: string;
            /** Kind */
            kind: string;
            /** Status */
            status: string;
            /** Statusrevision */
            statusRevision: number;
            /** Resource */
            resource: {
                [key: string]: unknown;
            };
            /** Result */
            result: {
                [key: string]: unknown;
            } | null;
            /** Error */
            error: {
                [key: string]: unknown;
            } | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /** Completedat */
            completedAt: string | null;
        };
        /** EnvironmentOperationView */
        EnvironmentOperationView: {
            operation: components["schemas"]["EnvironmentOperationSnapshot"];
            /** Outcome */
            outcome: {
                [key: string]: unknown;
            } | null;
        };
        /** EnvironmentOptionRead */
        EnvironmentOptionRead: {
            /** Value */
            value: string;
            /** Label */
            label: string;
        };
        /** EnvironmentPage */
        EnvironmentPage: {
            /** Items */
            items: components["schemas"]["EnvironmentView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** EnvironmentPatch */
        EnvironmentPatch: {
            /** Expectedmetadatarevision */
            expectedMetadataRevision: number;
            /** Name */
            name?: string | null;
            /** Notes */
            notes?: string | null;
        };
        /** EnvironmentProfile */
        EnvironmentProfile: {
            /** Name */
            name: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Revision
             * @default 0
             */
            revision: number;
            /** Imageid */
            imageId: string;
            /**
             * Width
             * @default 720
             */
            width: number;
            /**
             * Height
             * @default 1280
             */
            height: number;
            /**
             * Dpi
             * @default 320
             */
            dpi: number;
            /**
             * Cpu
             * @default 1
             */
            cpu: number;
            /**
             * Memorymb
             * @default 1536
             */
            memoryMb: number;
            /**
             * Locale
             * @default zh-CN
             */
            locale: string;
            /**
             * Timezone
             * @default Asia/Shanghai
             */
            timezone: string;
            /**
             * Shellroot
             * @default unknown
             * @enum {string}
             */
            shellRoot: "unknown" | "available" | "unavailable";
            /**
             * Applicationroot
             * @default unknown
             * @enum {string}
             */
            applicationRoot: "unknown" | "available" | "unavailable";
        };
        /** EnvironmentRefView */
        EnvironmentRefView: {
            /** Projectid */
            projectId: string;
            /** Environmentid */
            environmentId: string;
            /** Contentgeneration */
            contentGeneration: number;
            /** Metadatarevision */
            metadataRevision: number;
        };
        /** EnvironmentRepairRequest */
        EnvironmentRepairRequest: {
            /** Recordtargets */
            recordTargets?: components["schemas"]["RecordTargetWrite"][];
        };
        /** EnvironmentResourceLocator */
        EnvironmentResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "environment";
            /** Projectid */
            projectId: string;
            /** Environmentid */
            environmentId: string;
        };
        /** EnvironmentSaveRequest */
        EnvironmentSaveRequest: {
            /** Instanceid */
            instanceId: string;
            /**
             * Mode
             * @enum {string}
             */
            mode: "update" | "saveAs";
            /** Expectedusegeneration */
            expectedUseGeneration: number;
            /** Executiongeneration */
            executionGeneration: number;
            /** Currentexecutiongeneration */
            currentExecutionGeneration?: number | null;
            /** Name */
            name?: string | null;
            /** Notes */
            notes?: string | null;
            /** Expectedcontentgeneration */
            expectedContentGeneration?: number | null;
            /** Recordtargets */
            recordTargets?: components["schemas"]["RecordTargetWrite"][];
        };
        /** EnvironmentView */
        EnvironmentView: {
            ref: components["schemas"]["EnvironmentRefView"];
            /** Name */
            name: string;
            /** Notes */
            notes: string;
            /**
             * State
             * @enum {string}
             */
            state: "ready" | "unavailable" | "deleting" | "deleted";
            /** Profileid */
            profileId: string;
            /** Unavailablereason */
            unavailableReason: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /** Createdfromsource */
            createdFromSource?: string | null;
            /** Createdfromtaskid */
            createdFromTaskId?: string | null;
            /**
             * Linkedrecordcount
             * @default 0
             */
            linkedRecordCount: number;
        };
        /** ErrorResponse */
        ErrorResponse: {
            error: components["schemas"]["ApiError"];
        };
        /** ExcelExportCreate */
        ExcelExportCreate: {
            /** Selectiontoken */
            selectionToken: string;
            /** Datasetgeneration */
            datasetGeneration: string;
            /**
             * Scope
             * @enum {string}
             */
            scope: "all" | "filter";
            /** Filter */
            filter?: string | null;
            /** Orderby */
            orderBy?: string | null;
            /** Fieldids */
            fieldIds: string[];
            /** Includestatus */
            includeStatus: boolean;
        };
        /** ExcelExportResult */
        ExcelExportResult: {
            /** Filename */
            filename: string;
            /** Sha256 */
            sha256: string;
            /** Recordcount */
            recordCount: number;
        };
        /** ExcelImportResult */
        ExcelImportResult: {
            table: components["schemas"]["DataTableView"];
            /** Importedrecordcount */
            importedRecordCount: number;
            /** Previousdatasetgeneration */
            previousDatasetGeneration?: string | null;
        };
        /** ExcelInspectionCreate */
        ExcelInspectionCreate: {
            /** Selectiontoken */
            selectionToken: string;
        };
        /** ExcelInspectionResult */
        ExcelInspectionResult: {
            operation: components["schemas"]["ProjectOperationView"];
            inspection: components["schemas"]["ExcelInspectionView"];
        };
        /** ExcelInspectionView */
        ExcelInspectionView: {
            /** Inspectionid */
            inspectionId: string;
            /** Fingerprint */
            fingerprint: string;
            /** Filename */
            filename: string;
            /**
             * Expiresat
             * Format: date-time
             */
            expiresAt: string;
            /** Sheets */
            sheets: components["schemas"]["ExcelSheetInspection"][];
            /** Issues */
            issues: string[];
        };
        /** ExcelMapping */
        ExcelMapping: {
            /** Columnindex */
            columnIndex: number;
            /** Target */
            target: components["schemas"]["NewTarget"] | components["schemas"]["ExistingTarget"];
        };
        /** ExcelReconcileResult */
        ExcelReconcileResult: {
            /** Targetoperationid */
            targetOperationId: string;
            /**
             * Status
             * @enum {string}
             */
            status: "accepted" | "running" | "reconciling" | "succeeded" | "failed";
            /** Expectedtargetrevision */
            expectedTargetRevision?: number | null;
        };
        /** ExcelReplaceImpact */
        ExcelReplaceImpact: {
            target: components["schemas"]["TableResourceLocator"];
            /** Impactrevision */
            impactRevision: number;
            /** Expectedrevisions */
            expectedRevisions: {
                [key: string]: string | number;
            };
            /** Recordcount */
            recordCount: number;
            /** Blockers */
            blockers: string[];
            /**
             * Calculatedat
             * Format: date-time
             */
            calculatedAt: string;
        };
        /** ExcelSheetInspection */
        ExcelSheetInspection: {
            /** Sheetid */
            sheetId: string;
            /** Name */
            name: string;
            /** Headers */
            headers: string[];
            /** Sample */
            sample: (string | number | boolean | components["schemas"]["DataDateScalar"] | null)[][];
            /** Rowcount */
            rowCount: number;
            /** Ignoredemptyrowcount */
            ignoredEmptyRowCount: number;
            /** Formularowcount */
            formulaRowCount: number[];
            /** Identitycandidates */
            identityCandidates: number[];
            /** Issues */
            issues: string[];
        };
        /** ExcelTableImportCreate */
        ExcelTableImportCreate: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** Inspectionid */
            inspectionId: string;
            /** Fingerprint */
            fingerprint: string;
            /** Sheetid */
            sheetId: string;
            /** Mapping */
            mapping: components["schemas"]["ExcelMapping"][];
            /** Identity */
            identity: components["schemas"]["SystemExcelIdentity"] | components["schemas"]["ColumnExcelIdentity"];
        };
        /** ExcelTableReplace */
        ExcelTableReplace: {
            /** Inspectionid */
            inspectionId: string;
            /** Fingerprint */
            fingerprint: string;
            /** Sheetid */
            sheetId: string;
            /** Mapping */
            mapping: components["schemas"]["ExcelMapping"][];
            /** Identity */
            identity: components["schemas"]["SystemExcelIdentity"] | components["schemas"]["ColumnExcelIdentity"];
            /** Expecteddatasetgeneration */
            expectedDatasetGeneration: string;
            /** Expectedtablerevision */
            expectedTableRevision: number;
            /** Impactrevision */
            impactRevision: number;
        };
        /** ExistingTarget */
        ExistingTarget: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "existing";
            /** Fieldid */
            fieldId: string;
        };
        /** ExpectedRevision */
        ExpectedRevision: {
            /** Expected Revision */
            expected_revision: number;
        };
        /** FailureDestination */
        FailureDestination: {
            /** Automationid */
            automationId: string;
            /** Name */
            name: string;
            /** Count */
            count: number;
            /** Reasonsummary */
            reasonSummary?: string | null;
        };
        /** FieldEqualsRelation */
        FieldEqualsRelation: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "fieldEquals";
            /** Sourceinputid */
            sourceInputId: string;
            sourceFieldRef: components["schemas"]["DataFieldRef"];
            targetFieldRef: components["schemas"]["DataFieldRef"];
        };
        /** FieldImpactReport */
        FieldImpactReport: {
            /** Impactrevision */
            impactRevision: number;
            target: components["schemas"]["FieldResourceLocator"];
            /** Changedigest */
            changeDigest: string;
            /** Expectedrevisions */
            expectedRevisions: {
                [key: string]: number;
            };
            /** Impacts */
            impacts: components["schemas"]["DataMutationImpact"][];
            /** Blockers */
            blockers: components["schemas"]["DataMutationBlocker"][];
            /**
             * Calculatedat
             * Format: date-time
             */
            calculatedAt: string;
        };
        /** FieldImpactRequest */
        FieldImpactRequest: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "updateField";
            target: components["schemas"]["FieldResourceLocator"];
            change: components["schemas"]["DataFieldWrite"];
        };
        /** FieldMutationResult */
        FieldMutationResult: {
            field: components["schemas"]["DataFieldView"];
            /** Tablerevision */
            tableRevision: number;
            /**
             * Action
             * @enum {string}
             */
            action: "create" | "update";
        };
        /** FieldResourceLocator */
        FieldResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "field";
            fieldRef: components["schemas"]["DataFieldRef"];
        };
        /** FieldTableIdentity */
        FieldTableIdentity: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "field";
            /** Fieldid */
            fieldId: string;
        };
        /** FixedEnvironment */
        FixedEnvironment: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source: "fixedEnvironment";
            /** Environmentid */
            environmentId: string;
            /** Proxyoverride */
            proxyOverride?: (components["schemas"]["SourceDefaultProxy"] | components["schemas"]["NoProxy"] | components["schemas"]["FixedProxy"] | components["schemas"]["PoolProxy"]) | null;
            /** Modelproviderid */
            modelProviderId?: string | null;
        };
        /** FixedProxy */
        FixedProxy: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "fixed";
            /** Proxyid */
            proxyId: string;
        };
        /** FollowUpBatchRequest */
        FollowUpBatchRequest: {
            /**
             * Mode
             * @constant
             */
            mode: "originalInputGroup";
            /** Expectedtaskstatusrevision */
            expectedTaskStatusRevision: number;
            /** Parameteroverrides */
            parameterOverrides?: {
                [key: string]: string | number | boolean | null;
            };
        };
        /** GroupCreate */
        GroupCreate: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** Member Ids */
            member_ids: string[];
            /**
             * Acknowledge Risk
             * @default false
             */
            acknowledge_risk: boolean;
        };
        /** GroupPage */
        GroupPage: {
            /** Items */
            items: components["schemas"]["GroupView"][];
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
            /** Matched Count */
            matched_count: number;
        };
        /** GroupReferences */
        GroupReferences: {
            /** Profiles */
            profiles?: components["schemas"]["ResourceReference"][];
        };
        /** GroupUpdate */
        GroupUpdate: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** Member Ids */
            member_ids: string[];
            /**
             * Acknowledge Risk
             * @default false
             */
            acknowledge_risk: boolean;
            /** Expected Revision */
            expected_revision: number;
        };
        /** GroupView */
        GroupView: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Member Ids */
            member_ids: string[];
            /** Revision */
            revision: number;
            /** Reference Count */
            reference_count: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthResponse */
        HealthResponse: {
            /**
             * Status
             * @constant
             */
            status: "ok";
            /** Apiversion */
            apiVersion: string;
            /** Instanceid */
            instanceId: string;
        };
        /** HealthSnapshot */
        HealthSnapshot: {
            /**
             * State
             * @default untested
             * @enum {string}
             */
            state: "untested" | "checking" | "healthy" | "unhealthy";
            /** Latency Ms */
            latency_ms?: number | null;
            /** Exit Ip */
            exit_ip?: string | null;
            /** Checked At */
            checked_at?: string | null;
            /**
             * Source
             * @default none
             * @enum {string}
             */
            source: "local_probe" | "provider_probe" | "none";
            error?: components["schemas"]["ApiError"] | null;
        };
        /** Impact */
        Impact: {
            /** Code */
            code: string;
            /** Resource */
            resource: components["schemas"]["ProjectResourceLocator"] | components["schemas"]["AutomationResourceLocator"] | components["schemas"]["BatchResourceLocator"] | components["schemas"]["TaskResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["FieldResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"] | components["schemas"]["SyncResourceLocator"] | components["schemas"]["EnvironmentResourceLocator"];
            /** Message */
            message: string;
            /** Blocking */
            blocking: boolean;
        };
        /** InputDefinition */
        InputDefinition: {
            /** Inputid */
            inputId: string;
            /** Alias */
            alias: string;
            /** Tableid */
            tableId: string;
            /** Datasetgeneration */
            datasetGeneration: string;
            /**
             * Mode
             * @enum {string}
             */
            mode: "independent" | "fixedRecord" | "related";
            /** Required */
            required: boolean;
            fixedRecord?: components["schemas"]["DataRecordRef"] | null;
            /** Relation */
            relation?: (components["schemas"]["RecordSlotRelation"] | components["schemas"]["FieldEqualsRelation"] | components["schemas"]["SameRecordRelation"]) | null;
            /** Fieldbindings */
            fieldBindings: components["schemas"]["InputFieldBinding"][];
            /** Filter */
            filter: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Orderby */
            orderBy: {
                [key: string]: string;
            }[];
        };
        /** InputEnvironment */
        InputEnvironment: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source: "inputEnvironment";
            /** Inputid */
            inputId: string;
            /** Proxyoverride */
            proxyOverride?: (components["schemas"]["SourceDefaultProxy"] | components["schemas"]["NoProxy"] | components["schemas"]["FixedProxy"] | components["schemas"]["PoolProxy"]) | null;
            /** Modelproviderid */
            modelProviderId?: string | null;
        };
        /** InputFieldBinding */
        InputFieldBinding: {
            /** Inputfieldid */
            inputFieldId: string;
            /** Inputfieldalias */
            inputFieldAlias: string;
            fieldRef: components["schemas"]["DataFieldRef"];
        };
        /** InputPlan */
        InputPlan: {
            /** Inputs */
            inputs: components["schemas"]["InputDefinition"][];
        };
        /** InputPreviewItem */
        InputPreviewItem: {
            /** Inputid */
            inputId: string;
            /** Alias */
            alias: string;
            /** Tabledisplay */
            tableDisplay: string;
            /** Recorddisplay */
            recordDisplay: string | null;
            /** Values */
            values?: {
                [key: string]: components["schemas"]["JsonValue"];
            }[];
            /** Outcome */
            outcome: string;
            /** Required */
            required: boolean;
            /** Detail */
            detail?: string | null;
            /** Scannedcount */
            scannedCount?: number | null;
        };
        /** InputPreviewRequest */
        InputPreviewRequest: {
            /** Expectedautomationrevision */
            expectedAutomationRevision: number;
        };
        /** InputPreviewResponse */
        InputPreviewResponse: {
            /** Runnable */
            runnable: boolean;
            /** Selectionstatus */
            selectionStatus: string;
            /** Evaluatedcandidatebindings */
            evaluatedCandidateBindings: number;
            /** Inputs */
            inputs: components["schemas"]["InputPreviewItem"][];
        };
        /** InstalledKernelList */
        InstalledKernelList: {
            /** Items */
            items: components["schemas"]["InstalledKernelRead"][];
        };
        /** InstalledKernelRead */
        InstalledKernelRead: {
            /**
             * Edition
             * @enum {string}
             */
            edition: "public" | "licensed";
            /** Version */
            version: string;
            /** Executablepath */
            executablePath: string;
            /** Size */
            size: number;
        };
        /** IpAllowlist */
        IpAllowlist: {
            /** Enabled */
            enabled: boolean;
            /** Ipv4S */
            ipv4s: string[];
        };
        /** IpAllowlistUpdate */
        IpAllowlistUpdate: {
            /** Expected Revision */
            expected_revision: number;
            /** Enabled */
            enabled: boolean;
            /** Ipv4S */
            ipv4s: string[];
        };
        JsonValue: unknown;
        /** KernelCatalogRead */
        KernelCatalogRead: {
            /** Wrapperversion */
            wrapperVersion: string;
            /** Platform */
            platform: string;
            /** Releases */
            releases: components["schemas"]["KernelReleaseRead"][];
            /** Installed */
            installed: components["schemas"]["InstalledKernelRead"][];
            /** Catalogerror */
            catalogError: string | null;
        };
        /** KernelDownload */
        KernelDownload: {
            /**
             * Edition
             * @enum {string}
             */
            edition: "public" | "licensed";
            /** Version */
            version: string;
            /**
             * Releasechannel
             * @enum {string}
             */
            releaseChannel: "stable" | "preview";
        };
        /** KernelOperationList */
        KernelOperationList: {
            /** Items */
            items: components["schemas"]["KernelOperationRead"][];
        };
        /** KernelOperationRead */
        KernelOperationRead: {
            /** Id */
            id: string;
            /**
             * Edition
             * @enum {string}
             */
            edition: "public" | "licensed";
            /** Requestedversion */
            requestedVersion: string;
            /** Resolvedversion */
            resolvedVersion: string | null;
            /**
             * Releasechannel
             * @enum {string}
             */
            releaseChannel: "stable" | "preview";
            /**
             * State
             * @enum {string}
             */
            state: "queued" | "downloading" | "verifying" | "extracting" | "cancelling" | "cancelled" | "completed" | "failed";
            /** Progress */
            progress: number | null;
            /** Message */
            message: string | null;
            /** Error */
            error: string | null;
        };
        /** KernelRefRead */
        KernelRefRead: {
            /**
             * Edition
             * @enum {string}
             */
            edition: "public" | "licensed";
            /** Version */
            version: string;
        };
        /** KernelReleaseRead */
        KernelReleaseRead: {
            /**
             * Edition
             * @enum {string}
             */
            edition: "public" | "licensed";
            /** Version */
            version: string;
            /** Chromiumversion */
            chromiumVersion: string;
            /**
             * Releasechannel
             * @enum {string}
             */
            releaseChannel: "stable" | "preview";
            /** Publishedat */
            publishedAt: string | null;
            /** Archive */
            archive: string | null;
            /** Size */
            size: number | null;
            /** Installed */
            installed: boolean;
        };
        /** LicenseRead */
        LicenseRead: {
            /** Configured */
            configured: boolean;
            /** Valid */
            valid: boolean;
            /** Plan */
            plan: string | null;
            /** Expires */
            expires: string | null;
            seats: components["schemas"]["LicenseSeatsRead"] | null;
        };
        /** LicenseSeatsRead */
        LicenseSeatsRead: {
            /** Active */
            active: number | null;
            /** Limit */
            limit: number | null;
        };
        /** LicenseWrite */
        LicenseWrite: {
            /**
             * Licensekey
             * Format: password
             */
            licenseKey: string;
        };
        /** LocationList */
        LocationList: {
            /** Items */
            items: components["schemas"]["LocationView"][];
            /** Fetched At */
            fetched_at?: string | null;
            /** Stale */
            stale: boolean;
        };
        /** LocationView */
        LocationView: {
            /** Cities */
            cities?: string[];
            /** Country */
            country?: string | null;
            /** Available Slots */
            available_slots?: number | null;
            /** Id */
            id: string;
            /** City */
            city: string;
            /** Region */
            region?: string | null;
            /** Carrier */
            carrier?: string | null;
            /**
             * Availability
             * @default unknown
             * @enum {string}
             */
            availability: "available" | "unavailable" | "unknown";
        };
        /** MaintenanceDiscardRequest */
        MaintenanceDiscardRequest: {
            /** Maintenanceoperationid */
            maintenanceOperationId: string;
            /** Instanceid */
            instanceId: string;
        };
        /** MaintenanceStartRequest */
        MaintenanceStartRequest: {
            /** Expectedcontentgeneration */
            expectedContentGeneration: number;
        };
        /** ManualFinishRequest */
        ManualFinishRequest: {
            /** Expectedcheckpointrevision */
            expectedCheckpointRevision: number;
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "succeeded" | "failed";
            /** Reason */
            reason: string;
            /** Retainenvironment */
            retainEnvironment: {
                [key: string]: unknown;
            };
        };
        /** ManualItemPage */
        ManualItemPage: {
            /** Items */
            items: components["schemas"]["ManualItemView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
        };
        /** ManualItemView */
        ManualItemView: {
            /** Manualitemid */
            manualItemId: string;
            /** Projectid */
            projectId: string;
            /** Taskid */
            taskId: string;
            /** Runid */
            runId: string;
            /** Instanceid */
            instanceId: string | null;
            /** Checkpointrevision */
            checkpointRevision: number;
            /** Status */
            status: string;
            /** Statusrevision */
            statusRevision: number;
            /** Expiresat */
            expiresAt: string | null;
            /** Allowedtargets */
            allowedTargets: unknown[];
            /** Resumestarted */
            resumeStarted: boolean;
            /** Reason */
            reason: string | null;
            /** Createdat */
            createdAt?: string | null;
            /** Updatedat */
            updatedAt?: string | null;
        };
        /** ManualResumeRequest */
        ManualResumeRequest: {
            /** Checkpointrevision */
            checkpointRevision: number;
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
            /** Targetnodeid */
            targetNodeId?: string | null;
            /** Inputs */
            inputs?: {
                [key: string]: unknown;
            };
        };
        /** ModelDiscoveryRead */
        ModelDiscoveryRead: {
            /**
             * Ok
             * @default true
             * @constant
             */
            ok: true;
            /** Items */
            items: components["schemas"]["RemoteModel"][];
            /** Total */
            total: number;
            /** Latencyms */
            latencyMs: number;
            /** Endpoint */
            endpoint: string;
            /** Message */
            message: string;
        };
        /** ModelInput */
        ModelInput: {
            /** Modelkey */
            modelKey: string;
            /** Displayname */
            displayName: string;
            /** Tagsjson */
            tagsJson?: string[];
            /** Contextwindow */
            contextWindow?: number | null;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            /**
             * Description
             * @default
             */
            description: string;
        };
        /** ModelOption */
        ModelOption: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Providerid
             * Format: uuid
             */
            providerId: string;
            /** Providername */
            providerName: string;
            /** Modelkey */
            modelKey: string;
            /** Displayname */
            displayName: string;
            /** Tagsjson */
            tagsJson: string[];
        };
        /** ModelOptionListRead */
        ModelOptionListRead: {
            /** Items */
            items: components["schemas"]["ModelOption"][];
            /** Total */
            total: number;
        };
        /** ModelProviderConnectInput */
        ModelProviderConnectInput: {
            provider: components["schemas"]["ModelProviderCreateInput"];
            /** Selectedmodels */
            selectedModels?: components["schemas"]["ModelInput"][];
        };
        /** ModelProviderConnectionUpdateInput */
        ModelProviderConnectionUpdateInput: {
            /** Name */
            name: string;
            /** Presetid */
            presetId: string | null;
            /**
             * Providerkind
             * @enum {string}
             */
            providerKind: "openai" | "anthropic" | "gemini" | "openai-compatible" | "custom";
            /** Baseurl */
            baseUrl: string | null;
            /**
             * Apikey
             * Format: password
             */
            apiKey?: string;
            /** Enabled */
            enabled: boolean;
            /** Description */
            description: string;
        };
        /** ModelProviderCreateInput */
        ModelProviderCreateInput: {
            /** Name */
            name: string;
            /** Presetid */
            presetId?: string | null;
            /**
             * Providerkind
             * @default openai-compatible
             * @enum {string}
             */
            providerKind: "openai" | "anthropic" | "gemini" | "openai-compatible" | "custom";
            /** Baseurl */
            baseUrl?: string | null;
            /**
             * Apikey
             * Format: password
             */
            apiKey?: string;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            /**
             * Description
             * @default
             */
            description: string;
        };
        /** ModelProviderListRead */
        ModelProviderListRead: {
            /** Items */
            items: components["schemas"]["ModelProviderRead"][];
            /** Total */
            total: number;
        };
        /** ModelProviderMetadataUpdateInput */
        ModelProviderMetadataUpdateInput: {
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Enabled */
            enabled: boolean;
        };
        /** ModelProviderRead */
        ModelProviderRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Presetid */
            presetId: string | null;
            /**
             * Providerkind
             * @enum {string}
             */
            providerKind: "openai" | "anthropic" | "gemini" | "openai-compatible" | "custom";
            /** Baseurl */
            baseUrl: string | null;
            /** Apikeyconfigured */
            apiKeyConfigured: boolean;
            /** Enabled */
            enabled: boolean;
            /** Description */
            description: string;
            /** Models */
            models: components["schemas"]["ModelRead"][];
            /**
             * Connectionstatus
             * @enum {string}
             */
            connectionStatus: "untested" | "connected" | "failed";
            /** Lastcheckedat */
            lastCheckedAt: string | null;
            /** Lastchecklatencyms */
            lastCheckLatencyMs: number | null;
            /** Lastcheckmessage */
            lastCheckMessage: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** ModelRead */
        ModelRead: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Providerid
             * Format: uuid
             */
            providerId: string;
            /** Modelkey */
            modelKey: string;
            /** Displayname */
            displayName: string;
            /** Tagsjson */
            tagsJson: string[];
            /** Contextwindow */
            contextWindow: number | null;
            /** Enabled */
            enabled: boolean;
            /** Description */
            description: string;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** ModelTestInput */
        ModelTestInput: {
            /** Modelkey */
            modelKey: string;
        };
        /** ModelTestRead */
        ModelTestRead: {
            /**
             * Ok
             * @default true
             * @constant
             */
            ok: true;
            /** Modelkey */
            modelKey: string;
            /** Latencyms */
            latencyMs: number;
            /** Outputpreview */
            outputPreview: string;
            /** Reasoningpreview */
            reasoningPreview: string;
            /** Message */
            message: string;
        };
        /** NewFromProfile */
        NewFromProfile: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source: "newFromProfile";
            /** Profileid */
            profileId?: string | null;
            /** Proxyoverride */
            proxyOverride?: (components["schemas"]["SourceDefaultProxy"] | components["schemas"]["NoProxy"] | components["schemas"]["FixedProxy"] | components["schemas"]["PoolProxy"]) | null;
            /** Modelproviderid */
            modelProviderId?: string | null;
        };
        /** NewTarget */
        NewTarget: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "new";
            definition: components["schemas"]["DataFieldWrite"];
        };
        /** NoProxy */
        NoProxy: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "none";
        };
        /** NodeAttemptPage */
        NodeAttemptPage: {
            /** Items */
            items: components["schemas"]["NodeAttemptView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** NodeAttemptView */
        NodeAttemptView: {
            /** Nodevisitid */
            nodeVisitId: string;
            /** Nodeid */
            nodeId: string;
            /** Nodename */
            nodeName: string;
            /** Attempt */
            attempt: number;
            /**
             * Status
             * @enum {string}
             */
            status: "running" | "succeeded" | "failed";
            /** Startedat */
            startedAt: string | null;
            /** Completedat */
            completedAt: string | null;
            /** Error */
            error: {
                [key: string]: unknown;
            } | null;
        };
        /** OperationAccepted */
        OperationAccepted: {
            operation: components["schemas"]["ProjectOperationView"];
        };
        /** OperationView */
        OperationView: {
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Target Id */
            target_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "succeeded" | "failed" | "unknown";
            /** Resource Revision */
            resource_revision?: number | null;
            error?: components["schemas"]["ApiError"] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** ParameterDefinition */
        ParameterDefinition: {
            /** Parameterid */
            parameterId: string;
            /** Name */
            name: string;
            /** Description */
            description?: string;
            /**
             * Type
             * @enum {string}
             */
            type: "string" | "number" | "boolean";
            /** Required */
            required: boolean;
            /** Defaultvalue */
            defaultValue?: string | number | boolean | null;
        };
        /** PoolOption */
        PoolOption: {
            /** Id */
            id: string;
            /** Name */
            name: string;
        };
        /** PoolProxy */
        PoolProxy: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "pool";
            /** Proxypoolid */
            proxyPoolId: string;
        };
        /** ProbeRequest */
        ProbeRequest: {
            /**
             * Protocol
             * @default http
             * @enum {string}
             */
            protocol: "http" | "socks5";
        };
        /** ProfileDuplicate */
        ProfileDuplicate: {
            /** Name */
            name: string;
        };
        /** ProfileEnvironmentOptionsRead */
        ProfileEnvironmentOptionsRead: {
            /** Locales */
            locales: components["schemas"]["EnvironmentOptionRead"][];
            /** Timezones */
            timezones: components["schemas"]["EnvironmentOptionRead"][];
            /** Useragenttemplates */
            userAgentTemplates: components["schemas"]["EnvironmentOptionRead"][];
        };
        /** ProfileList */
        ProfileList: {
            /** Items */
            items: components["schemas"]["ProfileRead"][];
            /** Total */
            total: number;
        };
        /** ProfileRead */
        ProfileRead: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Starturl
             * @default about:blank
             */
            startUrl: string;
            /** Locale */
            locale?: string | null;
            /** Timezone */
            timezone?: string | null;
            /**
             * Geoip
             * @default false
             */
            geoip: boolean;
            /**
             * Headless
             * @default false
             */
            headless: boolean;
            /**
             * Humanize
             * @default false
             */
            humanize: boolean;
            /**
             * Humanpreset
             * @default default
             * @enum {string}
             */
            humanPreset: "default" | "careful";
            /** Useragent */
            userAgent?: string | null;
            viewportJson?: components["schemas"]["Viewport"] | null;
            /** Colorscheme */
            colorScheme?: ("light" | "dark" | "no-preference") | null;
            /** Extensionpathsjson */
            extensionPathsJson?: string[];
            /** Expertargsjson */
            expertArgsJson?: string[];
            /** Browserversion */
            browserVersion: string;
            /**
             * Browseredition
             * @default public
             * @enum {string}
             */
            browserEdition: "public" | "licensed";
            /**
             * Releasechannel
             * @default stable
             * @enum {string}
             */
            releaseChannel: "stable" | "preview";
            /**
             * Proxymode
             * @default none
             * @enum {string}
             */
            proxyMode: "none" | "proxy" | "pool";
            /** Proxyid */
            proxyId?: string | null;
            /** Proxypoolid */
            proxyPoolId?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Fingerprintseed */
            fingerprintSeed: number;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** ProfileTestBrowserList */
        ProfileTestBrowserList: {
            /** Items */
            items: components["schemas"]["ProfileTestBrowserStatusRead"][];
        };
        /** ProfileTestBrowserRead */
        ProfileTestBrowserRead: {
            /**
             * Sessionid
             * Format: uuid
             */
            sessionId: string;
            /**
             * Profileid
             * Format: uuid
             */
            profileId: string;
            /** Fingerprintseed */
            fingerprintSeed: number;
            /** Warning */
            warning?: string | null;
        };
        /** ProfileTestBrowserStatusRead */
        ProfileTestBrowserStatusRead: {
            /**
             * Profileid
             * Format: uuid
             */
            profileId: string;
            /** Sessionid */
            sessionId: string | null;
            /**
             * State
             * @enum {string}
             */
            state: "starting" | "running" | "stopping";
        };
        /** ProfileWrite */
        ProfileWrite: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Starturl
             * @default about:blank
             */
            startUrl: string;
            /** Locale */
            locale?: string | null;
            /** Timezone */
            timezone?: string | null;
            /**
             * Geoip
             * @default false
             */
            geoip: boolean;
            /**
             * Headless
             * @default false
             */
            headless: boolean;
            /**
             * Humanize
             * @default false
             */
            humanize: boolean;
            /**
             * Humanpreset
             * @default default
             * @enum {string}
             */
            humanPreset: "default" | "careful";
            /** Useragent */
            userAgent?: string | null;
            viewportJson?: components["schemas"]["Viewport"] | null;
            /** Colorscheme */
            colorScheme?: ("light" | "dark" | "no-preference") | null;
            /** Extensionpathsjson */
            extensionPathsJson?: string[];
            /** Expertargsjson */
            expertArgsJson?: string[];
            /** Browserversion */
            browserVersion: string;
            /**
             * Browseredition
             * @default public
             * @enum {string}
             */
            browserEdition: "public" | "licensed";
            /**
             * Releasechannel
             * @default stable
             * @enum {string}
             */
            releaseChannel: "stable" | "preview";
            /**
             * Proxymode
             * @default none
             * @enum {string}
             */
            proxyMode: "none" | "proxy" | "pool";
            /** Proxyid */
            proxyId?: string | null;
            /** Proxypoolid */
            proxyPoolId?: string | null;
        };
        /** ProjectBatchResult */
        ProjectBatchResult: {
            batch: components["schemas"]["BatchView"];
        };
        /** ProjectCapabilities */
        ProjectCapabilities: {
            /**
             * Automations
             * @constant
             */
            automations: "available";
            /**
             * Data
             * @constant
             */
            data: "available";
            /**
             * Runs
             * @constant
             */
            runs: "available";
            /**
             * Environments
             * @constant
             */
            environments: "available";
            /**
             * Statistics
             * @constant
             */
            statistics: "available";
            /**
             * Sync
             * @constant
             */
            sync: "available";
        };
        /** ProjectCreate */
        ProjectCreate: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            defaultResources?: components["schemas"]["ProjectDefaultResources"] | null;
        };
        /** ProjectDefaultResources */
        ProjectDefaultResources: {
            /** Profileid */
            profileId: string | null;
            /** Proxy */
            proxy: components["schemas"]["SourceDefaultProxy"] | components["schemas"]["NoProxy"] | components["schemas"]["FixedProxy"] | components["schemas"]["PoolProxy"];
            /** Modelproviderid */
            modelProviderId: string | null;
        };
        /** ProjectLifecycleImpact */
        ProjectLifecycleImpact: {
            /** Impactrevision */
            impactRevision: number;
            /** Blockers */
            blockers: components["schemas"]["Blocker"][];
            /** Impacts */
            impacts: components["schemas"]["Impact"][];
            /** Unsyncedcount */
            unsyncedCount: number;
        };
        /** ProjectOpenResult */
        ProjectOpenResult: {
            project: components["schemas"]["ProjectView"];
            /**
             * Lastopenedat
             * Format: date-time
             */
            lastOpenedAt: string;
        };
        /** ProjectOperationPage */
        ProjectOperationPage: {
            /** Items */
            items: components["schemas"]["ProjectOperationView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** ProjectOperationView */
        ProjectOperationView: {
            /** Operationid */
            operationId: string;
            /** Projectid */
            projectId: string | null;
            /** Idempotencykey */
            idempotencyKey: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "createProject" | "updateProject" | "createAutomation" | "updateAutomation" | "startBatch" | "stopBatch" | "forceStopBatch" | "followUpBatch" | "createTable" | "updateTable" | "mutateField" | "saveTableSchema" | "mutateStatus" | "createRecord" | "createRecords" | "updateRecord" | "setRecordStatus" | "deleteRecord" | "setRecordStatuses" | "cancelRecordStatuses" | "inspectExcel" | "importExcel" | "exportXlsx" | "reconcileOperation" | "connectSheets" | "disconnectSheets" | "inspectSheets" | "changeSheetsBinding" | "removeSheetsBinding" | "syncPull" | "syncPush" | "reconcileSync" | "archiveProject" | "restoreProject" | "deleteProject" | "deleteAutomation" | "deleteEnvironment";
            /**
             * Status
             * @enum {string}
             */
            status: "accepted" | "running" | "reconciling" | "succeeded" | "failed";
            /** Statusrevision */
            statusRevision: number;
            /** Resource */
            resource: components["schemas"]["ProjectResourceLocator"] | components["schemas"]["AutomationResourceLocator"] | components["schemas"]["BatchResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["FieldResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"];
            /** Result */
            result: components["schemas"]["ProjectView"] | components["schemas"]["AutomationView"] | components["schemas"]["ProjectBatchResult"] | components["schemas"]["DataTableView"] | components["schemas"]["FieldMutationResult"] | components["schemas"]["DataSchemaResult"] | components["schemas"]["StatusMutationResult"] | components["schemas"]["StatusDeleteResult"] | components["schemas"]["DataRecordView"] | components["schemas"]["DataRecordBatchResult"] | components["schemas"]["RecordDeleteResult"] | components["schemas"]["RecordStatusBatchOutcome"] | components["schemas"]["ExcelInspectionView"] | components["schemas"]["ExcelImportResult"] | components["schemas"]["ExcelExportResult"] | components["schemas"]["ExcelReconcileResult"] | components["schemas"]["CancelRecordStatusesResult"] | components["schemas"]["SheetsConnection"] | components["schemas"]["SheetsDisconnectResult"] | components["schemas"]["SheetsInspection"] | components["schemas"]["SheetsBinding"] | components["schemas"]["SheetsUnbindResult"] | components["schemas"]["SyncRunResult"] | components["schemas"]["SyncOperation"] | components["schemas"]["DeletedResourceResult"] | null;
            /** Error */
            error: {
                [key: string]: unknown;
            } | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /** Completedat */
            completedAt: string | null;
        };
        /** ProjectOverview */
        ProjectOverview: {
            project: components["schemas"]["ProjectView"];
            /** Counts */
            counts: {
                [key: string]: number;
            };
            availability: components["schemas"]["ProjectCapabilities"];
            /** Activity */
            activity: components["schemas"]["AttentionItem"][];
            /** Current */
            current: components["schemas"]["ActivityItem"][];
            /** Recent */
            recent: components["schemas"]["ActivityItem"][];
            dataChanges?: components["schemas"]["DataChanges"] | null;
        };
        /** ProjectPage */
        ProjectPage: {
            /** Items */
            items: components["schemas"]["ProjectSummary"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** ProjectPatch */
        ProjectPatch: {
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            defaultResources?: components["schemas"]["ProjectDefaultResources"] | null;
            /** Expectedmanagementrevision */
            expectedManagementRevision: number;
        };
        /** ProjectResourceLocator */
        ProjectResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "project";
            /** Projectid */
            projectId: string;
        };
        /** ProjectRunEventPage */
        ProjectRunEventPage: {
            /** Items */
            items: components["schemas"]["ProjectRunEventView"][];
            /** Aftersequence */
            afterSequence: number;
            /** Lastsequence */
            lastSequence: number;
            /** Hasmore */
            hasMore: boolean;
            /** Terminal */
            terminal: boolean;
        };
        /** ProjectRunEventView */
        ProjectRunEventView: {
            /** Eventid */
            eventId: string;
            /** Runid */
            runId: string;
            /** Sequence */
            sequence: number;
            /** Executiongeneration */
            executionGeneration: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "runStatus" | "nodeAttempt" | "log" | "output" | "artifact";
            /** Nodeid */
            nodeId?: string | null;
            /** Nodevisitid */
            nodeVisitId?: string | null;
            /** Attempt */
            attempt?: number | null;
            /**
             * Occurredat
             * Format: date-time
             */
            occurredAt: string;
            /** Payload */
            payload: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** ProjectRunOperationAccepted */
        ProjectRunOperationAccepted: {
            operation: components["schemas"]["ProjectRunOperationSnapshot"];
        };
        /** ProjectRunOperationSnapshot */
        ProjectRunOperationSnapshot: {
            /** Operationid */
            operationId: string;
            /** Projectid */
            projectId: string;
            /** Idempotencykey */
            idempotencyKey: string;
            /** Kind */
            kind: string;
            /** Status */
            status: string;
            /** Statusrevision */
            statusRevision: number;
            /** Resource */
            resource: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Result */
            result: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
            /** Error */
            error: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /** Completedat */
            completedAt: string | null;
        };
        /** ProjectStatistics */
        ProjectStatistics: {
            /** From */
            from: string;
            /** To */
            to: string;
            /** Timezone */
            timezone: string;
            sample: components["schemas"]["StatisticsSample"];
            /** Successrate */
            successRate?: number | null;
            /** Averagedurationms */
            averageDurationMs?: number | null;
            /** Trend */
            trend: components["schemas"]["StatisticsBucket"][];
            /** Failuresbyautomation */
            failuresByAutomation: components["schemas"]["FailureDestination"][];
            /** Resultsetid */
            resultSetId: string;
            /**
             * Calculatedat
             * Format: date-time
             */
            calculatedAt: string;
            /**
             * Expiresat
             * Format: date-time
             */
            expiresAt: string;
        };
        /** ProjectSummary */
        ProjectSummary: {
            /** Projectid */
            projectId: string;
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Managementrevision */
            managementRevision: number;
            /**
             * Lifecyclestate
             * @enum {string}
             */
            lifecycleState: "active" | "closing" | "archived" | "deleting" | "deleted";
            defaultResources: components["schemas"]["ProjectDefaultResources"];
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /** Lastopenedat */
            lastOpenedAt: string | null;
            availability: components["schemas"]["ProjectCapabilities"];
        };
        /** ProjectView */
        ProjectView: {
            /** Projectid */
            projectId: string;
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Managementrevision */
            managementRevision: number;
            /**
             * Lifecyclestate
             * @enum {string}
             */
            lifecycleState: "active" | "closing" | "archived" | "deleting" | "deleted";
            defaultResources: components["schemas"]["ProjectDefaultResources"];
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /** Lastopenedat */
            lastOpenedAt: string | null;
        };
        /** ProxyOption */
        ProxyOption: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Enabled */
            enabled: boolean;
        };
        /** ProxyOptionsRead */
        ProxyOptionsRead: {
            /** Proxies */
            proxies: components["schemas"]["ProxyOption"][];
            /** Pools */
            pools: components["schemas"]["PoolOption"][];
        };
        /** ProxyPage */
        ProxyPage: {
            /** Items */
            items: components["schemas"]["ProxyView"][];
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
            /** Matched Count */
            matched_count: number;
        };
        /** ProxyReferences */
        ProxyReferences: {
            /** Profiles */
            profiles?: components["schemas"]["ResourceReference"][];
            /** Groups */
            groups?: components["schemas"]["ResourceReference"][];
        };
        /** ProxyUpdate */
        ProxyUpdate: {
            /** Expected Revision */
            expected_revision: number;
            /** Name Override */
            name_override?: string | null;
            /** Enabled */
            enabled?: boolean | null;
        };
        /** ProxyView */
        ProxyView: {
            /** Id */
            id: string;
            /** Connection Id */
            connection_id: string;
            /** Name */
            name: string;
            /** Name Override */
            name_override?: string | null;
            /** Enabled */
            enabled: boolean;
            /** Remote Status */
            remote_status?: string | null;
            /** Remote Missing */
            remote_missing: boolean;
            /** Carrier */
            carrier?: string | null;
            /** City */
            city?: string | null;
            /** Region */
            region?: string | null;
            /** Exit Ip */
            exit_ip?: string | null;
            http_endpoint?: components["schemas"]["Endpoint"] | null;
            socks5_endpoint?: components["schemas"]["Endpoint"] | null;
            /** Credential Available */
            credential_available: boolean;
            health: components["schemas"]["HealthSnapshot"];
            /** Subscription Expires At */
            subscription_expires_at?: string | null;
            /** Last Synced At */
            last_synced_at?: string | null;
            /** Stale */
            stale: boolean;
            /** Revision */
            revision: number;
            /** Reference Count */
            reference_count: number;
            /** Capabilities */
            capabilities?: components["schemas"]["Capability"][];
        };
        /** ReconcileOperationCreate */
        ReconcileOperationCreate: {
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
        };
        /** RecordDelete */
        RecordDelete: {
            /** Datasetgeneration */
            datasetGeneration: string;
            /**
             * Recordkeytype
             * @enum {string}
             */
            recordKeyType: "text" | "integer" | "uuid";
            /** Expectedcontentrevision */
            expectedContentRevision: number;
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
            /** Expectedlinkrevision */
            expectedLinkRevision: number;
            /** Impactrevision */
            impactRevision: number;
        };
        /** RecordDeleteImpactRequest */
        RecordDeleteImpactRequest: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "deleteRecord";
            target: components["schemas"]["RecordResourceLocator"];
        };
        /** RecordDeleteResult */
        RecordDeleteResult: {
            target: components["schemas"]["RecordResourceLocator"];
            /**
             * Deleted
             * @constant
             */
            deleted: true;
        };
        /** RecordResourceLocator */
        RecordResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "record";
            recordRef: components["schemas"]["DataRecordRef"];
        };
        /** RecordSlotRelation */
        RecordSlotRelation: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "recordSlot";
            /** Slotid */
            slotId: string;
            /** Sourceinputid */
            sourceInputId: string;
        };
        /** RecordStatusBatchBlocker */
        RecordStatusBatchBlocker: {
            /** Code */
            code: string;
            /** Resource */
            resource: components["schemas"]["FieldResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"];
            /** State */
            state: string;
            /** Message */
            message: string;
            /** Details */
            details?: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** RecordStatusBatchCancel */
        RecordStatusBatchCancel: {
            /** Expectedoperationrevision */
            expectedOperationRevision: number;
        };
        /** RecordStatusBatchOutcome */
        RecordStatusBatchOutcome: {
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "processing" | "completed" | "conflicted" | "cancelled" | "failed";
            request: components["schemas"]["RecordStatusBatchRequest"];
            /** Blocks */
            blocks: components["schemas"]["RecordStatusBlock"][];
            /** Changedcount */
            changedCount: number;
            /** Conflictcount */
            conflictCount: number;
            /** Notstartedcount */
            notStartedCount: number;
            /** Cancelled */
            cancelled: boolean;
        };
        /** RecordStatusBatchPreview */
        RecordStatusBatchPreview: {
            request: components["schemas"]["RecordStatusBatchRequest"];
            /** Blocks */
            blocks: components["schemas"]["RecordStatusBlock"][];
            /** Checkedat */
            checkedAt: string;
        };
        /** RecordStatusBatchRequest */
        RecordStatusBatchRequest: {
            /** Statusid */
            statusId: string | null;
            /** Targets */
            targets: components["schemas"]["RecordStatusTarget"][];
            /**
             * Blocksize
             * @default 100
             */
            blockSize: number;
        };
        /** RecordStatusBlock */
        RecordStatusBlock: {
            /** Blockindex */
            blockIndex: number;
            /** Targets */
            targets: components["schemas"]["RecordStatusTarget"][];
            /**
             * State
             * @enum {string}
             */
            state: "notStarted" | "committed" | "conflicted";
            /** Blockers */
            blockers: components["schemas"]["RecordStatusBatchBlocker"][];
            /** Committedrevisions */
            committedRevisions: components["schemas"]["CommittedStatusRevision"][];
        };
        /** RecordStatusTarget */
        RecordStatusTarget: {
            recordRef: components["schemas"]["DataRecordRef"];
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
        };
        /** RecordTargetWrite */
        RecordTargetWrite: {
            /** Recordref */
            recordRef: {
                [key: string]: unknown;
            };
            /** Expectedlinkrevision */
            expectedLinkRevision: number;
            /**
             * Replaceallowed
             * @default false
             */
            replaceAllowed: boolean;
        };
        /** RelocateRequest */
        RelocateRequest: {
            /** Expected Revision */
            expected_revision: number;
            /** Location Id */
            location_id: string;
        };
        /** RemoteModel */
        RemoteModel: {
            /** Modelkey */
            modelKey: string;
            /** Displayname */
            displayName: string;
            /** Ownedby */
            ownedBy?: string | null;
            /** Contextwindow */
            contextWindow?: number | null;
        };
        /** RemoteStateView */
        RemoteStateView: {
            /** Status */
            status: string | null;
            /** City */
            city: string | null;
            /** Region */
            region: string | null;
            /** Carrier */
            carrier: string | null;
            /** Current Ip */
            current_ip: string | null;
            /** Bound */
            bound: boolean | null;
            /** Capabilities */
            capabilities: components["schemas"]["Capability"][];
            operation: components["schemas"]["OperationView"] | null;
            /**
             * Fetched At
             * Format: date-time
             */
            fetched_at: string;
        };
        /** ResourceReference */
        ResourceReference: {
            /** Id */
            id: string;
            /** Name */
            name: string;
        };
        /** RestoreProjectRequest */
        RestoreProjectRequest: {
            /** Expectedmanagementrevision */
            expectedManagementRevision: number;
        };
        /** RotationSchedule */
        RotationSchedule: {
            /** Enabled */
            enabled: boolean;
            /** Mode */
            mode?: ("same_city" | "same_city_carriers" | "full_pool") | null;
            /** Interval Minutes */
            interval_minutes?: number | null;
        };
        /** RotationScheduleUpdate */
        RotationScheduleUpdate: {
            /** Expected Revision */
            expected_revision: number;
            /**
             * Mode
             * @enum {string}
             */
            mode: "same_city" | "same_city_carriers" | "full_pool";
            /**
             * Interval Minutes
             * @enum {integer}
             */
            interval_minutes: 5 | 10 | 30 | 60;
        };
        /** RunArtifactPage */
        RunArtifactPage: {
            /** Items */
            items: components["schemas"]["RunArtifactView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** RunArtifactView */
        RunArtifactView: {
            /** Artifactid */
            artifactId: string;
            /**
             * Kind
             * @constant
             */
            kind: "screenshot";
            /**
             * Purpose
             * @constant
             */
            purpose: "error";
            /**
             * Availability
             * @enum {string}
             */
            availability: "available" | "unavailable";
            /** Nodeid */
            nodeId: string;
            /** Nodename */
            nodeName: string;
            /** Nodevisitid */
            nodeVisitId?: string | null;
            /** Eventsequence */
            eventSequence: number;
            /** Executiongeneration */
            executionGeneration: number;
            /** Mediatype */
            mediaType?: "image/png" | null;
            /** Bytesize */
            byteSize?: number | null;
            /** Sha256 */
            sha256?: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Unavailablereason */
            unavailableReason?: string | null;
            /** Contenturl */
            contentUrl?: string | null;
        };
        /** RunLogEntry */
        RunLogEntry: {
            /** Runid */
            runId: string;
            /** Sequence */
            sequence: number;
            /** Eventid */
            eventId: string;
            /** Executiongeneration */
            executionGeneration: number;
            /** Nodeid */
            nodeId?: string | null;
            /** Nodename */
            nodeName?: string | null;
            /** Nodevisitid */
            nodeVisitId?: string | null;
            /** Attempt */
            attempt?: number | null;
            /**
             * Level
             * @enum {string}
             */
            level: "debug" | "info" | "warning" | "error";
            /** Message */
            message: string;
            /**
             * Occurredat
             * Format: date-time
             */
            occurredAt: string;
        };
        /** RunLogPage */
        RunLogPage: {
            /** Items */
            items: components["schemas"]["RunLogEntry"][];
            /** Aftersequence */
            afterSequence: number;
            /** Lastsequence */
            lastSequence: number;
            /** Hasmore */
            hasMore: boolean;
        };
        /** RunOutputPage */
        RunOutputPage: {
            /** Items */
            items: components["schemas"]["RunOutputView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** RunOutputView */
        RunOutputView: {
            /** Outputid */
            outputId: string;
            /**
             * Kind
             * @constant
             */
            kind: "value";
            /** Name */
            name: string;
            value: components["schemas"]["JsonValue"];
            /** Runid */
            runId: string;
            /** Sequence */
            sequence: number;
            /** Nodeid */
            nodeId?: string | null;
            /** Nodename */
            nodeName?: string | null;
            /** Nodevisitid */
            nodeVisitId?: string | null;
            /** Attempt */
            attempt?: number | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
        };
        /** RunPolicy */
        RunPolicy: {
            /** Maxtasks */
            maxTasks: number;
            /** Concurrency */
            concurrency: number;
            /** Maxliveinstances */
            maxLiveInstances: number;
            /** Continueafterfailure */
            continueAfterFailure: boolean;
            /** Automaticexecutiontimeoutseconds */
            automaticExecutionTimeoutSeconds: number;
            /** Manualdeadlineseconds */
            manualDeadlineSeconds: number;
        };
        /** RunSnapshotView */
        RunSnapshotView: {
            /** Runid */
            runId: string;
            /** Runrequestid */
            runRequestId: string;
            /** Status */
            status: string;
            /** Statusrevision */
            statusRevision: number;
            /** Executiongeneration */
            executionGeneration: number;
            /** Preparedcontentid */
            preparedContentId: string;
            /** Capabilitybindings */
            capabilityBindings: {
                [key: string]: components["schemas"]["JsonValue"];
            }[];
            /** Resourcerequest */
            resourceRequest: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Lastsequence */
            lastSequence: number;
            /** Terminal */
            terminal: boolean;
            /** Error */
            error?: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
            /** Startedat */
            startedAt: string | null;
            /** Finishedat */
            finishedAt: string | null;
        };
        /** RuntimePaths */
        RuntimePaths: {
            /** Workspace */
            workspace: string;
            /** Database */
            database: string;
            /** Profiles */
            profiles: string;
            /** Kernels */
            kernels: string;
            /** Logs */
            logs: string;
        };
        /** RuntimeRead */
        RuntimeRead: {
            /** Apiversion */
            apiVersion: string;
            /** Backendversion */
            backendVersion: string;
            /** Pythonversion */
            pythonVersion: string;
            /** Sqliteversion */
            sqliteVersion: string;
            paths: components["schemas"]["RuntimePaths"];
            /** Blockers */
            blockers: string[];
        };
        /** SameRecordRelation */
        SameRecordRelation: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "sameRecord";
            /** Sourceinputid */
            sourceInputId: string;
        };
        /** SessionAction */
        SessionAction: {
            /** Generation */
            generation: number;
            /**
             * Action
             * @enum {string}
             */
            action: "end" | "embedded" | "native" | "takeover" | "resume";
            /**
             * Requestid
             * Format: uuid
             */
            requestId: string;
        };
        /** SessionCreate */
        SessionCreate: {
            /**
             * Requestid
             * Format: uuid
             */
            requestId: string;
            /**
             * Deviceid
             * Format: uuid
             */
            deviceId: string;
            /**
             * Access
             * @default manual
             * @enum {string}
             */
            access: "manual" | "readonly";
        };
        /** SessionRead */
        SessionRead: {
            /** Id */
            id: string;
            /** Deviceid */
            deviceId: string;
            /** Generation */
            generation: number;
            /**
             * Access
             * @enum {string}
             */
            access: "manual" | "readonly";
            /**
             * Endpoint
             * @default embedded
             * @enum {string}
             */
            endpoint: "embedded" | "native";
            /** State */
            state: string;
            /** Width */
            width: number;
            /** Height */
            height: number;
            /** Latestoperation */
            latestOperation?: string | null;
        };
        /** SheetsBinding */
        SheetsBinding: {
            /** Connectionid */
            connectionId: string;
            /** Spreadsheetid */
            spreadsheetId: string;
            /** Sheetid */
            sheetId: number;
            /** Spreadsheettitle */
            spreadsheetTitle?: string | null;
            /** Sheetname */
            sheetName?: string | null;
            /** Bindingepoch */
            bindingEpoch: number;
            identityStrategy: components["schemas"]["SheetsIdentityStrategy"];
            /** Mapping */
            mapping: components["schemas"]["SheetsMappingEntry"][];
            /** Syncpaused */
            syncPaused: boolean;
        };
        /**
         * SheetsBindingChange
         * @description The exact binding a caller intends to publish, minus its CAS revisions.
         */
        SheetsBindingChange: {
            /** Connectionid */
            connectionId: string;
            /** Spreadsheetid */
            spreadsheetId: string;
            /** Sheetid */
            sheetId: number;
            identityStrategy: components["schemas"]["SheetsIdentityStrategy"];
            /** Mapping */
            mapping: components["schemas"]["SheetsMappingEntry"][];
        };
        /** SheetsBindingDelete */
        SheetsBindingDelete: {
            /** Impactrevision */
            impactRevision: number;
            /** Expectedtablerevision */
            expectedTableRevision: number;
        };
        /**
         * SheetsBindingImpactRequest
         * @description First binding and rebinding share one confirmation: the published change.
         */
        SheetsBindingImpactRequest: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "changeSheetsBinding";
            target: components["schemas"]["TableResourceLocator"];
            change: components["schemas"]["SheetsBindingChange"];
        };
        /** SheetsBindingWrite */
        SheetsBindingWrite: {
            /** Connectionid */
            connectionId: string;
            /** Spreadsheetid */
            spreadsheetId: string;
            /** Sheetid */
            sheetId: number;
            identityStrategy: components["schemas"]["SheetsIdentityStrategy"];
            /** Mapping */
            mapping: components["schemas"]["SheetsMappingEntry"][];
            /** Impactrevision */
            impactRevision: number;
            /** Expectedtablerevision */
            expectedTableRevision: number;
            /** Expectedbindingepoch */
            expectedBindingEpoch?: number | null;
        };
        /** SheetsColumn */
        SheetsColumn: {
            /** Columnid */
            columnId: string;
            /** Name */
            name: string;
            /** Formula */
            formula: boolean;
        };
        /** SheetsConnection */
        SheetsConnection: {
            /** Connectionid */
            connectionId: string;
            /** Accountlabel */
            accountLabel: string;
            /**
             * Credentialstate
             * @enum {string}
             */
            credentialState: "available" | "missing" | "invalid";
            /** Readable */
            readable: boolean;
            /** Writable */
            writable: boolean;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** SheetsConnectionCreate */
        SheetsConnectionCreate: {
            /** Accountlabel */
            accountLabel: string;
            /** Authorizationtoken */
            authorizationToken: string;
        };
        /** SheetsConnectionDelete */
        SheetsConnectionDelete: {
            /** Impactrevision */
            impactRevision: number;
            /**
             * Mode
             * @enum {string}
             */
            mode: "disconnect" | "forgetCredential";
        };
        /** SheetsConnectionDirectory */
        SheetsConnectionDirectory: {
            /** Items */
            items: components["schemas"]["SheetsConnection"][];
        };
        /**
         * SheetsConnectionResourceLocator
         * @description The connection a Sheets command names, as the shared impact report sees it.
         */
        SheetsConnectionResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "sheetsConnection";
            /** Projectid */
            projectId: string;
            /** Connectionid */
            connectionId: string;
        };
        /** SheetsDisconnectChange */
        SheetsDisconnectChange: {
            /**
             * Mode
             * @enum {string}
             */
            mode: "disconnect" | "forgetCredential";
        };
        /**
         * SheetsDisconnectImpactRequest
         * @description The frozen `disconnectSheets` action of the shared impact contract.
         */
        SheetsDisconnectImpactRequest: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "disconnectSheets";
            target: components["schemas"]["SheetsConnectionResourceLocator"];
            change: components["schemas"]["SheetsDisconnectChange"];
        };
        /**
         * SheetsDisconnectResult
         * @description The frozen `disconnectSheets` result: what was revoked and in which mode.
         */
        SheetsDisconnectResult: {
            /** Connectionid */
            connectionId: string;
            /**
             * Mode
             * @enum {string}
             */
            mode: "disconnect" | "forgetCredential";
            /** Disconnected */
            disconnected: boolean;
        };
        /** SheetsIdentityStrategy */
        SheetsIdentityStrategy: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "column" | "system";
            /** Columnid */
            columnId?: string | null;
        };
        /** SheetsIdentitySummary */
        SheetsIdentitySummary: {
            /** Unique */
            unique: boolean;
            /** Missing */
            missing: number;
            /** Duplicates */
            duplicates: number;
        };
        /**
         * SheetsImpactReport
         * @description The confirmation a Sheets connection or binding command quotes back.
         */
        SheetsImpactReport: {
            /** Impactrevision */
            impactRevision: number;
            /** Target */
            target: components["schemas"]["TableResourceLocator"] | components["schemas"]["SheetsConnectionResourceLocator"];
            /** Changedigest */
            changeDigest: string;
            /** Expectedrevisions */
            expectedRevisions: {
                [key: string]: number;
            };
            /** Impacts */
            impacts: components["schemas"]["DataMutationImpact"][];
            /** Blockers */
            blockers: components["schemas"]["DataMutationBlocker"][];
            /**
             * Calculatedat
             * Format: date-time
             */
            calculatedAt: string;
        };
        /** SheetsInspection */
        SheetsInspection: {
            /** Valid */
            valid: boolean;
            /** Issues */
            issues: components["schemas"]["SheetsIssue"][];
            /** Columns */
            columns: components["schemas"]["SheetsColumn"][];
            identitySummary: components["schemas"]["SheetsIdentitySummary"];
            /** Overlaps */
            overlaps: components["schemas"]["SheetsOverlap"][];
            /** Spreadsheettitle */
            spreadsheetTitle?: string | null;
            /** Sheetname */
            sheetName?: string | null;
            /** Bindingepoch */
            bindingEpoch?: number | null;
        };
        /** SheetsInspectionCreate */
        SheetsInspectionCreate: {
            /** Connectionid */
            connectionId: string;
            /** Spreadsheetid */
            spreadsheetId: string;
            /** Sheetid */
            sheetId: number;
            identityStrategy: components["schemas"]["SheetsIdentityStrategy"];
            /** Mapping */
            mapping: components["schemas"]["SheetsMappingEntry"][];
        };
        /** SheetsInspectionResult */
        SheetsInspectionResult: {
            /** Operation */
            operation: {
                [key: string]: unknown;
            };
            inspection: components["schemas"]["SheetsInspection"];
        };
        /** SheetsIssue */
        SheetsIssue: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Columnid */
            columnId?: string | null;
        };
        /** SheetsMappingEntry */
        SheetsMappingEntry: {
            /** Fieldid */
            fieldId: string;
            /** Columnid */
            columnId: string;
            /**
             * Direction
             * @enum {string}
             */
            direction: "read" | "write" | "both";
            /** Formula */
            formula: boolean;
        };
        /** SheetsOverlap */
        SheetsOverlap: {
            /** Projectid */
            projectId: string;
            /** Tableid */
            tableId: string;
            /** Columnids */
            columnIds: string[];
        };
        /** SheetsUnbindChange */
        SheetsUnbindChange: {
            /**
             * Mode
             * @constant
             */
            mode: "remove";
        };
        /** SheetsUnbindImpactRequest */
        SheetsUnbindImpactRequest: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "removeSheetsBinding";
            target: components["schemas"]["TableResourceLocator"];
            change: components["schemas"]["SheetsUnbindChange"];
        };
        /**
         * SheetsUnbindResult
         * @description The frozen `removeSheetsBinding` result: the table is back to unconfigured.
         */
        SheetsUnbindResult: {
            table: components["schemas"]["DataTableView"];
            /** Unbound */
            unbound: boolean;
        };
        /** SourceDefaultProxy */
        SourceDefaultProxy: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "sourceDefault";
        };
        /** StatisticsBucket */
        StatisticsBucket: {
            /** Succeeded */
            succeeded: number;
            /** Failed */
            failed: number;
            /** Cancelled */
            cancelled: number;
            /** Timed Out */
            timed_out: number;
            /** Interrupted */
            interrupted: number;
            /**
             * Bucketstart
             * Format: date-time
             */
            bucketStart: string;
            /** Averagedurationms */
            averageDurationMs?: number | null;
        };
        /** StatisticsSample */
        StatisticsSample: {
            /** Succeeded */
            succeeded: number;
            /** Failed */
            failed: number;
            /** Cancelled */
            cancelled: number;
            /** Timed Out */
            timed_out: number;
            /** Interrupted */
            interrupted: number;
        };
        /** StatusDelete */
        StatusDelete: {
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
            /** Expectedtablerevision */
            expectedTableRevision: number;
            /** Impactrevision */
            impactRevision: number;
        };
        /** StatusDeleteImpactRequest */
        StatusDeleteImpactRequest: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "deleteStatus";
            target: components["schemas"]["StatusResourceLocator"];
        };
        /** StatusDeleteResult */
        StatusDeleteResult: {
            /**
             * Action
             * @constant
             */
            action: "delete";
            /** Statusid */
            statusId: string;
            /**
             * Deleted
             * @constant
             */
            deleted: true;
            /** Tablerevision */
            tableRevision: number;
        };
        /** StatusMutationResult */
        StatusMutationResult: {
            /**
             * Action
             * @enum {string}
             */
            action: "create" | "update";
            status: components["schemas"]["DataStatusView"];
            /** Tablerevision */
            tableRevision: number;
        };
        /** StatusResourceLocator */
        StatusResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "status";
            /** Projectid */
            projectId: string;
            /** Tableid */
            tableId: string;
            /** Statusid */
            statusId: string;
        };
        /** StudioCommandLookup */
        StudioCommandLookup: {
            /** Commandid */
            commandId: string;
            /** Success */
            success: boolean;
            /** Httpstatus */
            httpStatus: number;
        } & {
            [key: string]: unknown;
        };
        /** StudioCommandReceipt */
        StudioCommandReceipt: {
            /** Commandid */
            commandId: string;
            /** Success */
            success: boolean;
        } & {
            [key: string]: unknown;
        };
        /** StudioEventCommandRequest */
        StudioEventCommandRequest: {
            /** Commandid */
            commandId: string;
            /** Event */
            event: string;
            /** Data */
            data: {
                [key: string]: unknown;
            };
        };
        /** StudioInputPromptState */
        StudioInputPromptState: {
            /** Requestid */
            requestId: string;
            /** Workflowid */
            workflowId: string;
            /** Nodeid */
            nodeId: string;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "answered" | "cancelled" | "expired";
        };
        /** StudioRunResultPage */
        StudioRunResultPage: {
            /** Runid */
            runId: string;
            /** Workflowid */
            workflowId: string;
            /** Items */
            items: components["schemas"]["StudioRunResultRow"][];
            /** Total */
            total: number;
            /** Throughsequence */
            throughSequence: number;
            /** Nextcursor */
            nextCursor: number | null;
        };
        /** StudioRunResultRow */
        StudioRunResultRow: {
            /** Sequence */
            sequence: number;
            /** Nodeid */
            nodeId: string;
            /** Executionid */
            executionId: string;
            /** Values */
            values: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Largevalues */
            largeValues?: {
                [key: string]: string;
            };
        };
        /** StudioRunResultValue */
        StudioRunResultValue: {
            /** Runid */
            runId: string;
            /** Sequence */
            sequence: number;
            /** Key */
            key: string;
            value: components["schemas"]["JsonValue"];
        };
        /** SyncAbandonRequest */
        SyncAbandonRequest: {
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
            /** Reason */
            reason: string;
        };
        /** SyncEvidence */
        SyncEvidence: {
            /**
             * Checkedat
             * Format: date-time
             */
            checkedAt: string;
            /** Target */
            target: string;
            /** Fields */
            fields: string[];
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "matched" | "notMatched" | "ambiguous";
        };
        /** SyncOperation */
        SyncOperation: {
            /** Syncoperationid */
            syncOperationId: string;
            /** Projectid */
            projectId: string;
            /** Tableid */
            tableId: string;
            record?: components["schemas"]["DataRecordRef"] | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "pull" | "push" | "reconcile" | "binding" | "column" | "systemIdentity";
            /** Bindingepoch */
            bindingEpoch: number;
            /** Targetcontentrevision */
            targetContentRevision?: number | null;
            /**
             * Status
             * @enum {string}
             */
            status: "notApplicable" | "idle" | "pending" | "sending" | "verifying" | "confirmed" | "failed" | "unknown" | "paused";
            /** Statusrevision */
            statusRevision: number;
            /** Operationid */
            operationId?: string | null;
            evidence?: components["schemas"]["SyncEvidence"] | null;
            /** Error */
            error?: {
                [key: string]: unknown;
            } | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** SyncOperationPage */
        SyncOperationPage: {
            /** Items */
            items: components["schemas"]["SyncOperation"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
        };
        /** SyncPauseRequest */
        SyncPauseRequest: {
            /** Expectedbindingepoch */
            expectedBindingEpoch: number;
        };
        /** SyncPullRequest */
        SyncPullRequest: {
            /** Expectedtablerevision */
            expectedTableRevision: number;
        };
        /** SyncPushRequest */
        SyncPushRequest: {
            /**
             * Mode
             * @enum {string}
             */
            mode: "due" | "allPending";
            /** Expectedbindingepoch */
            expectedBindingEpoch: number;
        };
        /** SyncResourceLocator */
        SyncResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "sync";
            /** Projectid */
            projectId: string;
            /** Tableid */
            tableId: string;
            /** Syncoperationid */
            syncOperationId: string;
        };
        /**
         * SyncRunResult
         * @description The frozen result of one pull or push command.
         *
         *     Per-record outcomes live on their own sync operations; the command result
         *     only says which table it ran on and what the queue looks like afterwards,
         *     so an accepted command is never mistaken for a finished sync.
         */
        SyncRunResult: {
            /** Tableid */
            tableId: string;
            summary: components["schemas"]["SyncSummary"];
        };
        /** SyncSnapshot */
        SyncSnapshot: {
            /** Last Synced At */
            last_synced_at?: string | null;
            /** Stale */
            stale: boolean;
            /**
             * Completeness
             * @enum {string}
             */
            completeness: "complete" | "partial" | "unknown";
            /** Synced Count */
            synced_count: number;
            /** Provider Total */
            provider_total?: number | null;
            /** Remote Missing Count */
            remote_missing_count: number;
            last_error?: components["schemas"]["ApiError"] | null;
        };
        /** SyncStateView */
        SyncStateView: {
            summary: components["schemas"]["SyncSummary"];
            binding?: components["schemas"]["SheetsBinding"] | null;
        };
        /** SyncStatusRevisionRequest */
        SyncStatusRevisionRequest: {
            /** Expectedstatusrevision */
            expectedStatusRevision: number;
        };
        /** SyncSummary */
        SyncSummary: {
            /**
             * Status
             * @enum {string}
             */
            status: "notApplicable" | "idle" | "pending" | "sending" | "verifying" | "confirmed" | "failed" | "unknown" | "paused";
            /** Pendingcount */
            pendingCount: number;
            /** Unknowncount */
            unknownCount: number;
            /** Lastconfirmedat */
            lastConfirmedAt?: string | null;
        };
        /** SystemExcelIdentity */
        SystemExcelIdentity: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "system";
        };
        /** SystemTableIdentity */
        SystemTableIdentity: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "system";
        };
        /** TableResourceLocator */
        TableResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "table";
            /** Projectid */
            projectId: string;
            /** Tableid */
            tableId: string;
        };
        /** TableSlotDefinition */
        TableSlotDefinition: {
            /** Slotid */
            slotId: string;
            /** Name */
            name: string;
            /** Targettableid */
            targetTableId: string;
            /** Required */
            required: boolean;
        };
        /** TableSyncSummary */
        TableSyncSummary: {
            /**
             * Status
             * @enum {string}
             */
            status: "notApplicable" | "idle" | "pending" | "sending" | "verifying" | "confirmed" | "failed" | "unknown" | "paused";
            /** Pendingcount */
            pendingCount: number;
            /** Unknowncount */
            unknownCount: number;
            /** Lastconfirmedat */
            lastConfirmedAt?: string | null;
        };
        /** TaskCurrentInputView */
        TaskCurrentInputView: {
            /** Inputid */
            inputId?: string | null;
            /** Recordref */
            recordRef: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Exists */
            exists: boolean;
            /** Values */
            values?: {
                [key: string]: components["schemas"]["JsonValue"];
            }[];
            /** Recordstatus */
            recordStatus?: string | null;
            /** Contentrevision */
            contentRevision?: number | null;
            /** Updatedat */
            updatedAt?: string | null;
            /** Changedfieldids */
            changedFieldIds?: string[];
        };
        /** TaskDataWriteView */
        TaskDataWriteView: {
            /** Kind */
            kind: string;
            /** Tabledisplay */
            tableDisplay: string;
            /** Recorddisplay */
            recordDisplay: string;
            /** Outcome */
            outcome: string;
            /** Nodeid */
            nodeId?: string | null;
            /** Nodename */
            nodeName?: string | null;
            /** Previousstatus */
            previousStatus?: string | null;
            /** Nextstatus */
            nextStatus?: string | null;
            /** Referencedisplay */
            referenceDisplay?: string | null;
            /** Beforesummary */
            beforeSummary?: string | null;
            /** Aftersummary */
            afterSummary?: string | null;
            /** Detail */
            detail?: string | null;
        };
        /** TaskDetail */
        TaskDetail: {
            /** Automationname */
            automationName?: string | null;
            /** Batchstartedat */
            batchStartedAt?: string | null;
            /** Parameterdefinitions */
            parameterDefinitions?: components["schemas"]["ParameterDefinition"][];
            /** Nodenames */
            nodeNames?: {
                [key: string]: string;
            };
            task: components["schemas"]["TaskView"];
            inputSnapshot: components["schemas"]["TaskInputSnapshotView"];
            /** Currentinputs */
            currentInputs?: components["schemas"]["TaskCurrentInputView"][];
            run: components["schemas"]["RunSnapshotView"];
            /** Datawrites */
            dataWrites?: components["schemas"]["TaskDataWriteView"][];
            cleanup: components["schemas"]["CleanupSummaryView"];
        };
        /** TaskInputSnapshotView */
        TaskInputSnapshotView: {
            /** Inputsnapshotid */
            inputSnapshotId: string;
            /** Taskid */
            taskId: string;
            /** Batchid */
            batchId: string;
            /** Parameters */
            parameters: {
                [key: string]: string | number | boolean | null;
            };
            /** Inputs */
            inputs: {
                [key: string]: components["schemas"]["JsonValue"];
            }[];
            /**
             * Capturedat
             * Format: date-time
             */
            capturedAt: string;
        };
        /** TaskPage */
        TaskPage: {
            /** Items */
            items: components["schemas"]["TaskView"][];
            /** Page */
            page: number;
            /** Pagesize */
            pageSize: number;
            /** Total */
            total: number;
            /** Sort */
            sort: string;
        };
        /** TaskResourceLocator */
        TaskResourceLocator: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "task";
            /** Projectid */
            projectId: string;
            /** Taskid */
            taskId: string;
        };
        /** TaskView */
        TaskView: {
            /** Taskid */
            taskId: string;
            /** Projectid */
            projectId: string;
            /** Batchid */
            batchId: string;
            /** Runid */
            runId: string;
            /** Runrequestid */
            runRequestId: string;
            /** Status */
            status: string;
            /** Statusrevision */
            statusRevision: number;
            /** Inputsnapshotid */
            inputSnapshotId: string;
            /** Taskordinal */
            taskOrdinal: number;
            /** Automationname */
            automationName?: string | null;
            /** Batchstartedat */
            batchStartedAt?: string | null;
            /** Inputidentifier */
            inputIdentifier?: string | null;
            /** Endnodename */
            endNodeName?: string | null;
            /** Laststatusat */
            lastStatusAt?: string | null;
            /** Manualitemid */
            manualItemId?: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Completedat */
            completedAt?: string | null;
        };
        /** UsagePoint */
        UsagePoint: {
            /**
             * At
             * Format: date-time
             */
            at: string;
            /** Value */
            value: number;
        };
        /** UsageView */
        UsageView: {
            /** Available */
            available: boolean;
            /** Unit */
            unit?: string | null;
            /** Total */
            total?: number | null;
            /** Points */
            points?: components["schemas"]["UsagePoint"][];
            /** Fetched At */
            fetched_at?: string | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** Viewport */
        Viewport: {
            /** Width */
            width: number;
            /** Height */
            height: number;
        };
        /** WorkflowCatalogDetail */
        WorkflowCatalogDetail: {
            /** Workflowid */
            workflowId: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Checksum */
            checksum: string;
            validation: components["schemas"]["WorkflowCatalogValidation"];
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** WorkflowCatalogIssue */
        WorkflowCatalogIssue: {
            /** Nodeid */
            nodeId: string | null;
            /** Path */
            path: string[];
            /** Code */
            code: string;
            /** Message */
            message: string;
        };
        /** WorkflowCatalogItem */
        WorkflowCatalogItem: {
            /** Workflowid */
            workflowId: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Checksum */
            checksum: string;
            validation: components["schemas"]["WorkflowCatalogValidation"];
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
        };
        /** WorkflowCatalogList */
        WorkflowCatalogList: {
            /** Items */
            items: components["schemas"]["WorkflowCatalogItem"][];
        };
        /** WorkflowCatalogValidation */
        WorkflowCatalogValidation: {
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "blocked";
            /** Runnable */
            runnable: boolean;
            /** Issues */
            issues: components["schemas"]["WorkflowCatalogIssue"][];
        };
        /** WorkflowExecuteRequest */
        WorkflowExecuteRequest: {
            /** Runid */
            runId: string;
            /** Documentid */
            documentId: string;
            /** Profileid */
            profileId: string;
            /**
             * Headless
             * @default false
             */
            headless: boolean;
            /** Document */
            document?: {
                [key: string]: unknown;
            } | null;
        } & {
            [key: string]: unknown;
        };
        /** WorkflowStopRequest */
        WorkflowStopRequest: {
            /** Runid */
            runId: string;
        };
        /** WorkflowUpdate */
        WorkflowUpdate: {
            /** Clientrequestid */
            clientRequestId: string;
            /** Expectedrevision */
            expectedRevision: number;
        } & {
            [key: string]: unknown;
        };
        /** WorkflowWrite */
        WorkflowWrite: {
            /** Clientrequestid */
            clientRequestId: string;
        } & {
            [key: string]: unknown;
        };
        /** StudioBrowserPage */
        StudioBrowserPage: {
            /** Pageid */
            pageId: string;
            /** Title */
            title: string;
            /** Url */
            url: string;
        };
        /** StudioBrowserPageCommand */
        StudioBrowserPageCommand: {
            /** Sessionid */
            sessionId: string;
            /** Expectedrevision */
            expectedRevision: number;
            /** Pageid */
            pageId: string;
            /**
             * Action
             * @enum {string}
             */
            action: "select" | "focus" | "navigate";
            /**
             * Url
             * @default null
             */
            url: string | null;
        };
        /** StudioBrowserPages */
        StudioBrowserPages: {
            /** Sessionid */
            sessionId: string;
            /** Revision */
            revision: number;
            /** Targetpageid */
            targetPageId: string | null;
            /** Pages */
            pages: components["schemas"]["StudioBrowserPage"][];
        };
        /** StudioBrowserScriptContext */
        StudioBrowserScriptContext: {
            /** Browsersessionid */
            browserSessionId: string;
            /** Pageid */
            pageId: string;
            /** Revision */
            revision: number;
            /** Url */
            url: string;
            /** Activerequestid */
            activeRequestId: string | null;
        };
        /** StudioBrowserScriptRequest */
        StudioBrowserScriptRequest: {
            /** Requestid */
            requestId: string;
            context: components["schemas"]["StudioBrowserScriptTarget"];
            /** Code */
            code: string;
            /** Variables */
            variables: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** StudioBrowserScriptState */
        StudioBrowserScriptState: {
            /** Requestid */
            requestId: string;
            context: components["schemas"]["StudioBrowserScriptTarget"];
            /**
             * Status
             * @enum {string}
             */
            status: "running" | "completed" | "failed" | "cancelled" | "expired";
            /** Hasresult */
            hasResult: boolean;
            result: components["schemas"]["JsonValue"];
            /** Error */
            error: string | null;
            /**
             * Executionkind
             * @enum {string}
             */
            executionKind: "browser" | "mock";
        };
        /** StudioBrowserScriptTarget */
        StudioBrowserScriptTarget: {
            /** Browsersessionid */
            browserSessionId: string;
            /** Pageid */
            pageId: string;
            /** Revision */
            revision: number;
        };
        /** StudioBrowserStatus */
        StudioBrowserStatus: {
            /** Isopen */
            isOpen: boolean;
            /** Pickeractive */
            pickerActive: boolean;
        } & {
            [key: string]: unknown;
        };
        /** StudioClaimedRequestState */
        StudioClaimedRequestState: {
            /** Requestid */
            requestId: string;
            /** Workflowid */
            workflowId: string;
            /** Nodeid */
            nodeId: string;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "claimed" | "completed" | "failed" | "expired";
            /**
             * Claimid
             * @default null
             */
            claimId: string | null;
        };
        /** StudioConditionalRequired */
        StudioConditionalRequired: {
            /** Field */
            field: string;
            /** Default */
            default: string | null;
            /** Map */
            map: {
                [key: string]: string[];
            };
        };
        /** StudioCredentialConfirmed */
        StudioCredentialConfirmed: {
            /**
             * Success
             * @constant
             */
            success: true;
        };
        /** StudioCredentialField */
        StudioCredentialField: {
            /** Key */
            key: string;
            /** Masked */
            masked: string;
        };
        /** StudioCredentialFieldRemove */
        StudioCredentialFieldRemove: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "remove";
            /** Key */
            key: string;
        };
        /** StudioCredentialFieldRename */
        StudioCredentialFieldRename: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "rename";
            /** Key */
            key: string;
            /** Newkey */
            newKey: string;
        };
        /** StudioCredentialFieldsCommand */
        StudioCredentialFieldsCommand: {
            /** Commandid */
            commandId: string;
            /** Name */
            name: string;
            /** Expectedrevision */
            expectedRevision: number;
            /** Operations */
            operations: (components["schemas"]["StudioCredentialFieldRename"] | components["schemas"]["StudioCredentialFieldRemove"])[];
        };
        /** StudioCredentialFieldsConfirmed */
        StudioCredentialFieldsConfirmed: {
            /**
             * Success
             * @constant
             */
            success: true;
            /** Commandid */
            commandId: string;
            credential: components["schemas"]["StudioCredentialItem"];
            /**
             * Mock
             * @default null
             */
            mock: boolean | null;
        };
        /** StudioCredentialItem */
        StudioCredentialItem: {
            /**
             * Revision
             * @default 1
             */
            revision: number;
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Fields */
            fields: components["schemas"]["StudioCredentialField"][];
            /** Created At */
            created_at: string;
            /** Updated At */
            updated_at: string;
        };
        /** StudioCredentialList */
        StudioCredentialList: {
            /**
             * Success
             * @constant
             */
            success: true;
            /** Credentials */
            credentials: components["schemas"]["StudioCredentialItem"][];
            /**
             * Mock
             * @default null
             */
            mock: boolean | null;
        };
        /** StudioCredentialNames */
        StudioCredentialNames: {
            /**
             * Success
             * @constant
             */
            success: true;
            /** Names */
            names: string[];
        };
        /** StudioCredentialRenameRequest */
        StudioCredentialRenameRequest: {
            /** Old Name */
            old_name: string;
            /** New Name */
            new_name: string;
        };
        /** StudioCredentialSaved */
        StudioCredentialSaved: {
            /**
             * Success
             * @constant
             */
            success: true;
            /** Name */
            name: string;
            /**
             * Mock
             * @default null
             */
            mock: boolean | null;
        };
        /** StudioCredentialUpsertRequest */
        StudioCredentialUpsertRequest: {
            /** Name */
            name: string;
            /** Fields */
            fields: {
                [key: string]: string;
            };
            /**
             * Description
             * @default null
             */
            description: string | null;
        };
        /** StudioDebugControlLookup */
        StudioDebugControlLookup: {
            /** Runid */
            runId: string;
            /** Pauseid */
            pauseId: string;
            /** Controlrevision */
            controlRevision: number;
            /** Commandid */
            commandId: string;
            /** Workflowid */
            workflowId: string;
            /**
             * Action
             * @enum {string}
             */
            action: "resume" | "step";
            /** Success */
            success: boolean;
            /** Error */
            error: string | null;
            /** Httpstatus */
            httpStatus: number;
        } & {
            [key: string]: unknown;
        };
        /** StudioDebugControlReceipt */
        StudioDebugControlReceipt: {
            /** Runid */
            runId: string;
            /** Pauseid */
            pauseId: string;
            /** Controlrevision */
            controlRevision: number;
            /** Commandid */
            commandId: string;
            /** Workflowid */
            workflowId: string;
            /**
             * Action
             * @enum {string}
             */
            action: "resume" | "step";
            /** Success */
            success: boolean;
            /** Error */
            error: string | null;
        } & {
            [key: string]: unknown;
        };
        /** StudioDebugControlRequest */
        StudioDebugControlRequest: {
            /** Runid */
            runId: string;
            /** Pauseid */
            pauseId: string;
            /** Controlrevision */
            controlRevision: number;
            /** Commandid */
            commandId: string;
        };
        /** StudioDebugPauseContext */
        StudioDebugPauseContext: {
            /** Runid */
            runId: string;
            /** Pauseid */
            pauseId: string;
            /** Controlrevision */
            controlRevision: number;
        };
        /** StudioDebugVariableChange */
        StudioDebugVariableChange: {
            /** Name */
            name: string;
            value: components["schemas"]["JsonValue"];
        };
        /** StudioDebugVariablesReceipt */
        StudioDebugVariablesReceipt: {
            /** Runid */
            runId: string;
            /** Pauseid */
            pauseId: string;
            /** Controlrevision */
            controlRevision: number;
            /** Commandid */
            commandId: string;
            /** Changes */
            changes: components["schemas"]["StudioDebugVariableChange"][];
            /** Workflowid */
            workflowId: string;
            /** Success */
            success: boolean;
            /** Error */
            error: string | null;
        } & {
            [key: string]: unknown;
        };
        /** StudioDebugVariablesRequest */
        StudioDebugVariablesRequest: {
            /** Runid */
            runId: string;
            /** Pauseid */
            pauseId: string;
            /** Controlrevision */
            controlRevision: number;
            /** Commandid */
            commandId: string;
            /** Changes */
            changes: components["schemas"]["StudioDebugVariableChange"][];
        };
        /** StudioExecutionLogEntry */
        StudioExecutionLogEntry: {
            /** Sequence */
            sequence: number;
            /** Id */
            id: string;
            /** Timestamp */
            timestamp: string;
            /**
             * Level
             * @enum {string}
             */
            level: "debug" | "info" | "success" | "warning" | "error";
            /** Message */
            message: string;
            /**
             * Nodeid
             * @default null
             */
            nodeId: string | null;
            /**
             * Duration
             * @default null
             */
            duration: number | null;
            /**
             * Details
             * @default null
             */
            details: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
        };
        /** StudioExecutionLogPage */
        StudioExecutionLogPage: {
            /** Runid */
            runId: string;
            /** Workflowid */
            workflowId: string;
            /** Items */
            items: components["schemas"]["StudioExecutionLogEntry"][];
            /** Total */
            total: number;
            /**
             * Nextcursor
             * @default null
             */
            nextCursor: number | null;
        };
        /** StudioFileSelectRequest */
        StudioFileSelectRequest: {
            /**
             * Title
             * @default null
             */
            title: string | null;
            /**
             * Initialdir
             * @default null
             */
            initialDir: string | null;
            /**
             * Filetypes
             * @default null
             */
            fileTypes: string[][] | null;
        };
        /** StudioFolderSelectRequest */
        StudioFolderSelectRequest: {
            /**
             * Title
             * @default null
             */
            title: string | null;
            /**
             * Initialdir
             * @default null
             */
            initialDir: string | null;
        };
        /** StudioImageAsset */
        StudioImageAsset: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Originalname */
            originalName: string;
            /** Size */
            size: number;
            /** Uploadedat */
            uploadedAt: string;
            /** Folder */
            folder: string;
            /** Extension */
            extension: string;
            /**
             * Path
             * @default null
             */
            path: string | null;
        } & {
            [key: string]: unknown;
        };
        /** StudioImageFolderCreated */
        StudioImageFolderCreated: {
            /** Success */
            success: boolean;
            /** Path */
            path: string;
        };
        /** StudioImageFolderDeleted */
        StudioImageFolderDeleted: {
            /** Success */
            success: boolean;
            /** Deletedcount */
            deletedCount: number;
        };
        /** StudioImageFolderRenamed */
        StudioImageFolderRenamed: {
            /** Success */
            success: boolean;
            /** Newpath */
            newPath: string;
        };
        /** StudioImageMoved */
        StudioImageMoved: {
            /** Success */
            success: boolean;
            /** Newfolder */
            newFolder: string;
        };
        /** StudioImageMutationResult */
        StudioImageMutationResult: {
            /** Success */
            success: boolean;
        };
        /** StudioImageRenameResult */
        StudioImageRenameResult: {
            /** Success */
            success: boolean;
            asset: components["schemas"]["StudioImageAsset"];
        };
        /** StudioImageUploadResult */
        StudioImageUploadResult: {
            asset: components["schemas"]["StudioImageAsset"];
        };
        /** StudioInputPromptRequest */
        StudioInputPromptRequest: {
            /** Requestid */
            requestId: string;
            /** Variablename */
            variableName: string;
            /** Title */
            title: string;
            /** Message */
            message: string;
            /** Defaultvalue */
            defaultValue: string | number | boolean | null;
            /**
             * Inputmode
             * @enum {string}
             */
            inputMode: "single" | "multiline" | "number" | "integer" | "password" | "list" | "file" | "folder" | "checkbox" | "slider_int" | "slider_float" | "select_single" | "select_multiple";
            /**
             * Minvalue
             * @default null
             */
            minValue: number | null;
            /**
             * Maxvalue
             * @default null
             */
            maxValue: number | null;
            /**
             * Maxlength
             * @default null
             */
            maxLength: number | null;
            /**
             * Required
             * @default true
             */
            required: boolean;
            /**
             * Selectoptions
             * @default null
             */
            selectOptions: string[] | null;
        } & {
            [key: string]: unknown;
        };
        /** StudioInputPromptResult */
        StudioInputPromptResult: {
            /** Requestid */
            requestId: string;
            /** Value */
            value: string | null;
        };
        /** StudioJsScriptClaim */
        StudioJsScriptClaim: {
            /** Requestid */
            requestId: string;
            /** Claimid */
            claimId: string;
        };
        /** StudioJsScriptRequest */
        StudioJsScriptRequest: {
            /** Requestid */
            requestId: string;
            /** Workflowid */
            workflowId: string;
            /** Nodeid */
            nodeId: string;
            /** Code */
            code: string;
            /** Variables */
            variables: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        };
        /** StudioJsScriptResult */
        StudioJsScriptResult: {
            /** Requestid */
            requestId: string;
            /** Claimid */
            claimId: string;
            /** Success */
            success: boolean;
            /** @default null */
            result: components["schemas"]["JsonValue"];
            /**
             * Variables
             * @default null
             */
            variables: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
            /**
             * Error
             * @default null
             */
            error: string | null;
        };
        /** StudioJsScriptState */
        StudioJsScriptState: {
            /** Requestid */
            requestId: string;
            /** Workflowid */
            workflowId: string;
            /** Nodeid */
            nodeId: string;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "claimed" | "completed" | "failed" | "expired";
            /**
             * Claimid
             * @default null
             */
            claimId: string | null;
        };
        /** StudioMcpConfig */
        StudioMcpConfig: {
            /** Mcpservers */
            mcpServers: {
                [key: string]: components["schemas"]["StudioMcpServerConfig"];
            };
        } & {
            [key: string]: unknown;
        };
        /** StudioMcpConnected */
        StudioMcpConnected: {
            /** Name */
            name: string;
            /** Tool Count */
            tool_count: number;
            /** Transport */
            transport: string;
        } & {
            [key: string]: unknown;
        };
        /** StudioMcpFailed */
        StudioMcpFailed: {
            /** Name */
            name: string;
            /** Error */
            error: string;
        } & {
            [key: string]: unknown;
        };
        /** StudioMcpReloaded */
        StudioMcpReloaded: {
            /** Connected */
            connected: components["schemas"]["StudioMcpConnected"][];
            /** Failed */
            failed: components["schemas"]["StudioMcpFailed"][];
            /** Disabled */
            disabled: string[];
            /** Total Servers */
            total_servers: number;
        } & {
            [key: string]: unknown;
        };
        /** StudioMcpSaveRequest */
        StudioMcpSaveRequest: {
            config: components["schemas"]["StudioMcpConfig"];
        };
        /** StudioMcpSaved */
        StudioMcpSaved: {
            /**
             * Success
             * @constant
             */
            success: true;
            /**
             * Saved
             * @constant
             */
            saved: true;
        } & {
            [key: string]: unknown;
        };
        /** StudioMcpServerConfig */
        StudioMcpServerConfig: {
            /**
             * Transport
             * @default null
             */
            transport: string | null;
            /**
             * Command
             * @default null
             */
            command: string | null;
            /**
             * Args
             * @default null
             */
            args: string[] | null;
            /**
             * Env
             * @default null
             */
            env: {
                [key: string]: string;
            } | null;
            /**
             * Cwd
             * @default null
             */
            cwd: string | null;
            /**
             * Url
             * @default null
             */
            url: string | null;
            /**
             * Headers
             * @default null
             */
            headers: {
                [key: string]: string;
            } | null;
            /**
             * Disabled
             * @default null
             */
            disabled: boolean | null;
            /**
             * Autoapprove
             * @default null
             */
            autoApprove: string[] | null;
        } & {
            [key: string]: unknown;
        };
        /** StudioMcpServerStatus */
        StudioMcpServerStatus: {
            /** Name */
            name: string;
            /** Transport */
            transport: string;
            /** Disabled */
            disabled: boolean;
            /** Connected */
            connected: boolean;
            /** Tool Count */
            tool_count: number;
            /** Tools */
            tools: components["schemas"]["StudioMcpTool"][];
            /** Last Error */
            last_error: string | null;
            /** Connected At */
            connected_at: string | null;
            /** Auto Approve */
            auto_approve: string[];
        } & {
            [key: string]: unknown;
        };
        /** StudioMcpStatus */
        StudioMcpStatus: {
            /** Servers */
            servers: components["schemas"]["StudioMcpServerStatus"][];
            /** Total Tools Injected */
            total_tools_injected: number;
        } & {
            [key: string]: unknown;
        };
        /** StudioMcpTool */
        StudioMcpTool: {
            /** Name */
            name: string;
            /** Description */
            description: string;
        } & {
            [key: string]: unknown;
        };
        /** StudioModuleRequiredFields */
        StudioModuleRequiredFields: {
            /** Schemarevision */
            schemaRevision: string;
            /** Coveredmodules */
            coveredModules: string[];
            /** Requiredfields */
            requiredFields: {
                [key: string]: string[];
            };
            /** Conditionalrequired */
            conditionalRequired: {
                [key: string]: components["schemas"]["StudioConditionalRequired"];
            };
            /** Fieldlabels */
            fieldLabels: {
                [key: string]: {
                    [key: string]: string;
                };
            };
        };
        /** StudioPathSelectionResult */
        StudioPathSelectionResult: {
            /** Success */
            success: boolean;
            /** Path */
            path: string | null;
            /**
             * Message
             * @default null
             */
            message: string | null;
            /**
             * Error
             * @default null
             */
            error: string | null;
        } & {
            [key: string]: unknown;
        };
        /** StudioPickerSessionRequest */
        StudioPickerSessionRequest: {
            /** Sessionid */
            sessionId: string;
        };
        /** StudioPickerSessionStartRequest */
        StudioPickerSessionStartRequest: {
            /** Sessionid */
            sessionId: string;
            /**
             * Url
             * @default null
             */
            url: string | null;
            /**
             * Profileid
             * @default null
             */
            profileId: string | null;
        };
        /** StudioPickerSessionState */
        StudioPickerSessionState: {
            /**
             * Success
             * @constant
             */
            success: true;
            /** Sessionid */
            sessionId: string;
            /** Active */
            active: boolean;
            /**
             * Selected
             * @default false
             */
            selected: boolean;
        } & {
            [key: string]: unknown;
        };
        /** StudioRecorderBatch */
        StudioRecorderBatch: {
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean;
            /** Success */
            success: boolean;
            /** Sessionid */
            sessionId: string;
            /** Nextseq */
            nextSeq: number;
            /** Data */
            data: components["schemas"]["StudioRecorderEvent"][];
        } & {
            [key: string]: unknown;
        };
        /** StudioRecorderEvent */
        StudioRecorderEvent: {
            /** Sequence */
            sequence: number;
            /**
             * Type
             * @enum {string}
             */
            type: "navigate" | "click" | "dblclick" | "input" | "select" | "check" | "keypress" | "drag" | "upload" | "scroll";
        } & {
            [key: string]: unknown;
        };
        /** StudioRecorderReadRequest */
        StudioRecorderReadRequest: {
            /** Sessionid */
            sessionId: string;
            /**
             * Afterseq
             * @default 0
             */
            afterSeq: number;
        };
        /** StudioRecorderStartRequest */
        StudioRecorderStartRequest: {
            /** Sessionid */
            sessionId: string;
        };
        /** StudioRecorderStarted */
        StudioRecorderStarted: {
            /** Success */
            success: boolean;
            /** Sessionid */
            sessionId: string;
            /** Recording */
            recording: boolean;
            /** Nextseq */
            nextSeq: number;
        } & {
            [key: string]: unknown;
        };
        /** StudioRecorderStatus */
        StudioRecorderStatus: {
            /**
             * Success
             * @constant
             */
            success: true;
            /**
             * Sessionid
             * @default null
             */
            sessionId: string | null;
            /** Recording */
            recording: boolean;
            /** Nextseq */
            nextSeq: number;
        } & {
            [key: string]: unknown;
        };
        /** StudioRecorderStopped */
        StudioRecorderStopped: {
            /**
             * Hasmore
             * @default false
             */
            hasMore: boolean;
            /** Success */
            success: boolean;
            /** Sessionid */
            sessionId: string;
            /** Nextseq */
            nextSeq: number;
            data: components["schemas"]["StudioRecorderTail"];
        } & {
            [key: string]: unknown;
        };
        /** StudioRecorderTail */
        StudioRecorderTail: {
            /** Events */
            events: components["schemas"]["StudioRecorderEvent"][];
        } & {
            [key: string]: unknown;
        };
        /** StudioRecordingReview */
        StudioRecordingReview: {
            /** Documentid */
            documentId: string;
            /** Revision */
            revision: number;
            /** Autowait */
            autoWait: boolean;
            /** Events */
            events: components["schemas"]["StudioRecorderEvent"][];
        };
        /** StudioRecordingReviewWrite */
        StudioRecordingReviewWrite: {
            /** Expectedrevision */
            expectedRevision: number;
            /** Autowait */
            autoWait: boolean;
            /** Events */
            events: components["schemas"]["StudioRecorderEvent"][];
        };
        /** StudioRequestClaim */
        StudioRequestClaim: {
            /** Requestid */
            requestId: string;
            /** Claimid */
            claimId: string;
        };
        /** StudioRetentionCleanup */
        StudioRetentionCleanup: {
            /**
             * Success
             * @constant
             */
            success: true;
            /**
             * Mock
             * @default null
             */
            mock: boolean | null;
            recordings: components["schemas"]["StudioRetentionCleanupEntry"];
            data: components["schemas"]["StudioRetentionCleanupEntry"];
        };
        /** StudioRetentionCleanupEntry */
        StudioRetentionCleanupEntry: {
            /** Removed */
            removed: number;
            /** Freedmb */
            freedMB: number;
        };
        /** StudioRetentionConfig */
        StudioRetentionConfig: {
            /** Enabled */
            enabled: boolean;
            /** Recordings Max Days */
            recordings_max_days: number;
            /** Recordings Max Total Mb */
            recordings_max_total_mb: number;
            /** Data Max Days */
            data_max_days: number;
            /** Data Max Total Mb */
            data_max_total_mb: number;
            /** Cleanup Interval Hours */
            cleanup_interval_hours: number;
        };
        /** StudioRetentionLoaded */
        StudioRetentionLoaded: {
            /**
             * Success
             * @constant
             */
            success: true;
            /**
             * Mock
             * @default null
             */
            mock: boolean | null;
            config: components["schemas"]["StudioRetentionConfig"];
            usage: components["schemas"]["StudioRetentionUsage"];
        };
        /** StudioRetentionSaved */
        StudioRetentionSaved: {
            /**
             * Success
             * @constant
             */
            success: true;
            /**
             * Mock
             * @default null
             */
            mock: boolean | null;
            config: components["schemas"]["StudioRetentionConfig"];
        };
        /** StudioRetentionUpdate */
        StudioRetentionUpdate: {
            /**
             * Enabled
             * @default null
             */
            enabled: boolean | null;
            /**
             * Recordings Max Days
             * @default null
             */
            recordings_max_days: number | null;
            /**
             * Recordings Max Total Mb
             * @default null
             */
            recordings_max_total_mb: number | null;
            /**
             * Data Max Days
             * @default null
             */
            data_max_days: number | null;
            /**
             * Data Max Total Mb
             * @default null
             */
            data_max_total_mb: number | null;
            /**
             * Cleanup Interval Hours
             * @default null
             */
            cleanup_interval_hours: number | null;
        };
        /** StudioRetentionUsage */
        StudioRetentionUsage: {
            recordings: components["schemas"]["StudioRetentionUsageEntry"];
            data: components["schemas"]["StudioRetentionUsageEntry"];
        };
        /** StudioRetentionUsageEntry */
        StudioRetentionUsageEntry: {
            /** Count */
            count: number;
            /** Sizemb */
            sizeMB: number;
        };
        /** StudioRetentionUsageResponse */
        StudioRetentionUsageResponse: {
            /**
             * Success
             * @constant
             */
            success: true;
            /**
             * Mock
             * @default null
             */
            mock: boolean | null;
            usage: components["schemas"]["StudioRetentionUsage"];
        };
        /** StudioRunVariableTrackingCleared */
        StudioRunVariableTrackingCleared: {
            /** Message */
            message: string;
            /** Runid */
            runId: string;
        };
        /** StudioRunVariableTrackingPage */
        StudioRunVariableTrackingPage: {
            /** Runid */
            runId: string;
            /** Tracking */
            tracking: components["schemas"]["StudioRunVariableTrackingRecord"][];
            /** Total */
            total: number;
            /** Throughsequence */
            throughSequence: number;
            /**
             * Nextcursor
             * @default null
             */
            nextCursor: number | null;
        };
        /** StudioRunVariableTrackingRecord */
        StudioRunVariableTrackingRecord: {
            /** Timestamp */
            timestamp: string;
            /** Variable Name */
            variable_name: string;
            old_value: components["schemas"]["JsonValue"];
            new_value: components["schemas"]["JsonValue"];
            /** Node Id */
            node_id: string;
            /** Node Name */
            node_name: string;
            /**
             * Operation
             * @enum {string}
             */
            operation: "create" | "update";
            /** Value Type */
            value_type: string;
            /** Sequence */
            sequence: number;
            /** Executionid */
            executionId: string;
            /** Largevalues */
            largeValues?: {
                [key: string]: string;
            };
        };
        /** StudioSelectorAttempt */
        StudioSelectorAttempt: {
            /** Selector */
            selector: string;
            /**
             * Count
             * @default null
             */
            count: number | null;
            /**
             * Error
             * @default null
             */
            error: string | null;
        };
        /** StudioSelectorElement */
        StudioSelectorElement: {
            /**
             * Tag
             * @default null
             */
            tag: string | null;
            /**
             * Text
             * @default null
             */
            text: string | null;
        };
        /** StudioSelectorTestRequest */
        StudioSelectorTestRequest: {
            /** Selector */
            selector: string;
            /**
             * Hints
             * @default null
             */
            hints: {
                [key: string]: unknown;
            } | null;
            /**
             * Highlight
             * @default true
             */
            highlight: boolean;
            /**
             * Sessionid
             * @default null
             */
            sessionId: string | null;
        };
        /** StudioSelectorTestResult */
        StudioSelectorTestResult: {
            /**
             * Success
             * @constant
             */
            success: true;
            /** Matched */
            matched: boolean;
            /** Count */
            count: number;
            /**
             * Matchedselector
             * @default null
             */
            matchedSelector: string | null;
            /**
             * Isprimary
             * @default null
             */
            isPrimary: boolean | null;
            /** @default null */
            element: components["schemas"]["StudioSelectorElement"] | null;
            /**
             * Tried
             * @default null
             */
            tried: components["schemas"]["StudioSelectorAttempt"][] | null;
            /**
             * Error
             * @default null
             */
            error: string | null;
        };
        /** StudioSimilarElements */
        StudioSimilarElements: {
            /** Pattern */
            pattern: string;
            /** Count */
            count: number;
            /** Minindex */
            minIndex: number;
            /** Maxindex */
            maxIndex: number;
            /**
             * Indices
             * @default null
             */
            indices: number[] | null;
            /**
             * Selector1
             * @default null
             */
            selector1: string | null;
            /**
             * Selector2
             * @default null
             */
            selector2: string | null;
        };
        /** StudioSimilarPickerResult */
        StudioSimilarPickerResult: {
            /** Selected */
            selected: boolean;
            /** Active */
            active: boolean;
            /** @default null */
            similar: components["schemas"]["StudioSimilarElements"] | null;
        };
        /** StudioSpeechRequest */
        StudioSpeechRequest: {
            /** Requestid */
            requestId: string;
            /** Workflowid */
            workflowId: string;
            /** Nodeid */
            nodeId: string;
            /** Text */
            text: string;
            /** Lang */
            lang: string;
            /** Rate */
            rate: number;
            /** Pitch */
            pitch: number;
            /** Volume */
            volume: number;
        };
        /** StudioSpeechResult */
        StudioSpeechResult: {
            /** Requestid */
            requestId: string;
            /** Claimid */
            claimId: string;
            /** Success */
            success: boolean;
            /**
             * Error
             * @default null
             */
            error: string | null;
        };
        /** StudioSpeechState */
        StudioSpeechState: {
            /** Requestid */
            requestId: string;
            /** Workflowid */
            workflowId: string;
            /** Nodeid */
            nodeId: string;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "claimed" | "completed" | "failed" | "expired";
            /**
             * Claimid
             * @default null
             */
            claimId: string | null;
        };
        /** StudioVariableTrackingCleared */
        StudioVariableTrackingCleared: {
            /** Message */
            message: string;
        };
        /** StudioVariableTrackingRecord */
        StudioVariableTrackingRecord: {
            /** Timestamp */
            timestamp: string;
            /** Variable Name */
            variable_name: string;
            old_value: components["schemas"]["JsonValue"];
            new_value: components["schemas"]["JsonValue"];
            /** Node Id */
            node_id: string;
            /** Node Name */
            node_name: string;
            /**
             * Operation
             * @enum {string}
             */
            operation: "create" | "update";
            /** Value Type */
            value_type: string;
        };
        /** StudioVariableTrackingResult */
        StudioVariableTrackingResult: {
            /** Tracking */
            tracking: components["schemas"]["StudioVariableTrackingRecord"][];
            /** Count */
            count: number;
        } & {
            [key: string]: unknown;
        };
        /** StudioWorkflowRunPage */
        StudioWorkflowRunPage: {
            /** Items */
            items: components["schemas"]["StudioWorkflowRunSummary"][];
            /** Total */
            total: number;
            /**
             * Nextcursor
             * @default null
             */
            nextCursor: number | null;
        };
        /** StudioWorkflowRunSummary */
        StudioWorkflowRunSummary: {
            /** Runid */
            runId: string;
            /** Workflowid */
            workflowId: string;
            /** Documentid */
            documentId: string;
            /** Workflowname */
            workflowName: string;
            /**
             * Status
             * @enum {string}
             */
            status: "starting" | "running" | "paused" | "completed" | "failed" | "stopped" | "interrupted";
            /** Startedat */
            startedAt: string;
            /**
             * Finishedat
             * @default null
             */
            finishedAt: string | null;
            /** Logcount */
            logCount: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
};
export type $defs = Record<string, never>;
export interface operations {
    list_connections_api_v1_proxy_panel_connections_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionList"];
                };
            };
        };
    };
    create_connection_api_v1_proxy_panel_connections_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionView"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Bad Gateway */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    delete_connection_api_v1_proxy_panel_connections__connection_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    update_connection_api_v1_proxy_panel_connections__connection_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectionUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionView"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    replace_api_key_api_v1_proxy_panel_connections__connection_id__api_key_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApiKeyUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionView"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Bad Gateway */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    verify_connection_api_v1_proxy_panel_connections__connection_id__verify_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmptyCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult_ConnectionView_"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Bad Gateway */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    sync_connection_api_v1_proxy_panel_connections__connection_id__sync_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmptyCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult_SyncSnapshot_"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Bad Gateway */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_proxies_api_v1_proxies_get: {
        parameters: {
            query?: {
                connection_id?: string | null;
                q?: string | null;
                carrier?: string | null;
                city?: string | null;
                health?: string | null;
                enabled?: boolean | null;
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProxyPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_proxy_api_v1_proxies__projection_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProxyView"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_proxy_api_v1_proxies__projection_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProxyUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProxyView"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    proxy_references_api_v1_proxies__projection_id__references_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProxyReferences"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    check_proxy_health_api_v1_proxies__projection_id__probe_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProbeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult_HealthSnapshot_"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    unavailable_get_ip_auth_api_v1_proxies__projection_id__ip_auth_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IpAllowlist"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    unavailable_set_ip_auth_api_v1_proxies__projection_id__ip_auth_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IpAllowlistUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult_IpAllowlist_"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_credentials_metadata_api_v1_proxies__projection_id__credentials_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CredentialView"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    unavailable_rotate_credentials_api_v1_proxies__projection_id__credentials_rotate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExpectedRevision"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult_CredentialView_"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    unavailable_usage_api_v1_proxies__projection_id__usage_get: {
        parameters: {
            query: {
                since: string;
                until: string;
            };
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UsageView"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    unavailable_account_summary_api_v1_proxy_panel_connections__connection_id__account_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountSummary"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_groups_api_v1_proxy_groups_get: {
        parameters: {
            query?: {
                q?: string | null;
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_group_api_v1_proxy_groups_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroupCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupView"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_group_api_v1_proxy_groups__group_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupView"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_group_api_v1_proxy_groups__group_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroupUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupView"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    delete_group_api_v1_proxy_groups__group_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    group_references_api_v1_proxy_groups__group_id__references_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupReferences"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remote_state_api_v1_proxies__projection_id__remote_state_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RemoteStateView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    locations_api_v1_proxy_panel_connections__connection_id__locations_get: {
        parameters: {
            query?: {
                q?: string;
                carrier?: string;
            };
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LocationList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    schedule_api_v1_proxies__projection_id__rotation_schedule_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RotationSchedule"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    save_rotation_api_v1_proxies__projection_id__rotation_schedule_put: {
        parameters: {
            query?: never;
            header: {
                "idempotency-key": string;
            };
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RotationScheduleUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    clear_rotation_api_v1_proxies__projection_id__rotation_schedule_delete: {
        parameters: {
            query?: never;
            header: {
                "idempotency-key": string;
            };
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExpectedRevision"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    change_ip_api_v1_proxies__projection_id__change_ip_post: {
        parameters: {
            query?: never;
            header: {
                "idempotency-key": string;
            };
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExpectedRevision"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    relocate_api_v1_proxies__projection_id__relocate_post: {
        parameters: {
            query?: never;
            header: {
                "idempotency-key": string;
            };
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RelocateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    latest_operation_api_v1_proxies__projection_id__operation_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationView"] | null;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_operation_api_v1_proxy_operations__operation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reconcile_operation_api_v1_proxy_operations__operation_id__reconcile_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    acknowledge_unknown_api_v1_proxy_operations__operation_id__acknowledge_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    list_profiles_api_v1_profiles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileList"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    create_profile_api_v1_profiles_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProfileWrite"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    environment_options_api_v1_profiles_environment_options_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileEnvironmentOptionsRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_test_browsers_api_v1_profiles_test_browsers_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileTestBrowserList"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_profile_api_v1_profiles__profile_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    update_profile_api_v1_profiles__profile_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProfileWrite"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    delete_profile_api_v1_profiles__profile_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    duplicate_profile_api_v1_profiles__profile_id__duplicate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProfileDuplicate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    regenerate_fingerprint_api_v1_profiles__profile_id__regenerate_fingerprint_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    open_test_browser_api_v1_profiles__profile_id__test_browser_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileTestBrowserRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    close_test_browser_api_v1_profiles__profile_id__test_browser_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                profile_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_proxy_options_api_v1_proxy_options_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProxyOptionsRead"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_providers_api_v1_model_providers_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelProviderListRead"];
                };
            };
        };
    };
    preview_api_v1_model_providers_connection_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModelProviderCreateInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelDiscoveryRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    connect_api_v1_model_providers_connect_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModelProviderConnectInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelProviderRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_provider_api_v1_model_providers__provider_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelProviderRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_metadata_api_v1_model_providers__provider_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModelProviderMetadataUpdateInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelProviderRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_provider_api_v1_model_providers__provider_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    test_provider_api_v1_model_providers__provider_id__test_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelDiscoveryRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    discover_api_v1_model_providers__provider_id__models_discover_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelDiscoveryRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    test_model_api_v1_model_providers__provider_id__models_test_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModelTestInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelTestRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_connection_api_v1_model_providers__provider_id__connection_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModelProviderConnectionUpdateInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelProviderRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_model_api_v1_model_providers__provider_id__models_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModelInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_model_api_v1_models__model_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                model_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModelInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_model_api_v1_models__model_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                model_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    options_api_v1_models_options_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelOptionListRead"];
                };
            };
        };
    };
    get_catalog_api_v1_kernels_catalog_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KernelCatalogRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_installed_api_v1_kernels_installed_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstalledKernelList"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    check_update_api_v1_kernels_check_update_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KernelCatalogRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_license_api_v1_kernels_license_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LicenseRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    connect_license_api_v1_kernels_license_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LicenseWrite"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LicenseRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    disconnect_license_api_v1_kernels_license_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_default_api_v1_kernels_default_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DefaultKernelRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    set_default_api_v1_kernels_default_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DefaultKernelWrite"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DefaultKernelRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    download_api_v1_kernels_download_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KernelDownload"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KernelOperationRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_operations_api_v1_kernels_operations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KernelOperationList"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    cancel_api_v1_kernels_operations__operation_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KernelOperationRead"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    remove_api_v1_kernels__version__delete: {
        parameters: {
            query: {
                edition: "public" | "licensed";
            };
            header?: never;
            path: {
                version: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    runtime_api_v1_settings_runtime_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RuntimeRead"];
                };
            };
        };
    };
    dashboard_api_v1_dashboard_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DashboardRead"];
                };
            };
        };
    };
    events_api_v1_kernels_events_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    list_workflows_api_v1_workflows_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkflowCatalogList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_workflow_api_v1_workflows__workflowId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workflowId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkflowCatalogDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_projects_api_v1_projects_get: {
        parameters: {
            query?: {
                q?: string | null;
                lifecycleState?: ("active" | "archived") | null;
                page?: number;
                pageSize?: number;
                sort?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    create_project_api_v1_projects_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectCreate"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectView"];
                };
            };
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_project_api_v1_projects__projectId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectSummary"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    delete_project_api_v1_projects__projectId__delete: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeleteProjectRequest"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    patch_project_api_v1_projects__projectId__patch: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    open_project_api_v1_projects__projectId__open_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOpenResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    overview_api_v1_projects__projectId__overview_get: {
        parameters: {
            query?: {
                timezone?: string | null;
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOverview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    operations_api_v1_projects__projectId__operations_get: {
        parameters: {
            query?: {
                page?: number;
                pageSize?: number;
                kind?: ("createProject" | "updateProject" | "createAutomation" | "updateAutomation" | "startBatch" | "stopBatch" | "forceStopBatch" | "followUpBatch" | "createTable" | "updateTable" | "mutateField" | "saveTableSchema" | "mutateStatus" | "createRecord" | "createRecords" | "updateRecord" | "setRecordStatus" | "deleteRecord" | "setRecordStatuses" | "cancelRecordStatuses" | "inspectExcel" | "importExcel" | "exportXlsx" | "reconcileOperation" | "archiveProject" | "restoreProject" | "deleteProject" | "deleteAutomation") | null;
                status?: ("accepted" | "running" | "reconciling" | "succeeded" | "failed") | null;
                resourceType?: ("project" | "table" | "field" | "status" | "record" | "automation" | "batch") | null;
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOperationPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    operation_api_v1_projects__projectId__operations__operationId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                operationId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    operation_by_key_api_v1_projects__projectId__operations_by_idempotency_key__key__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    workspace_operation_api_v1_workspace_operations_by_idempotency_key__key__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    lifecycle_impact_api_v1_projects__projectId__lifecycle_impact_get: {
        parameters: {
            query: {
                action: "archive" | "delete";
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectLifecycleImpact"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    archive_project_api_v1_projects__projectId__archive_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchiveProjectRequest"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    restore_project_api_v1_projects__projectId__restore_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RestoreProjectRequest"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    project_statistics_api_v1_projects__projectId__statistics_get: {
        parameters: {
            query?: {
                from?: string | null;
                to?: string | null;
                timezone?: string | null;
                automationId?: string | null;
                tableId?: string | null;
                interval?: "day" | "week" | "month";
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectStatistics"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    statistics_tasks_api_v1_projects__projectId__statistics__resultSetId__tasks_get: {
        parameters: {
            query: {
                result: "succeeded" | "failed" | "cancelled" | "timed_out" | "interrupted";
                intervalStart?: string | null;
                page?: number;
                pageSize?: number;
                sort?: string;
            };
            header?: never;
            path: {
                projectId: string;
                resultSetId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    start_batch_api_v1_projects__projectId__automations__automationId__batches_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                automationId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BatchStartRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectRunOperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    follow_up_batch_api_v1_projects__projectId__tasks__taskId__follow_up_batches_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                taskId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FollowUpBatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectRunOperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    preview_inputs_api_v1_projects__projectId__automations__automationId__input_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                automationId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InputPreviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InputPreviewResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    stop_batch_api_v1_projects__projectId__batches__batchId__stop_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                batchId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BatchStopRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectRunOperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    force_stop_batch_api_v1_projects__projectId__batches__batchId__force_stop_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                batchId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BatchStopRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectRunOperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_batches_api_v1_projects__projectId__batches_get: {
        parameters: {
            query?: {
                q?: string | null;
                automationId?: string | null;
                status?: string | null;
                startedFrom?: string | null;
                startedTo?: string | null;
                page?: number;
                pageSize?: number;
                sort?: string;
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BatchPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_batch_api_v1_projects__projectId__batches__batchId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                batchId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BatchDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tasks_api_v1_projects__projectId__tasks_get: {
        parameters: {
            query?: {
                q?: string | null;
                batchId?: string | null;
                automationId?: string | null;
                status?: string | null;
                endedFrom?: string | null;
                endedTo?: string | null;
                page?: number;
                pageSize?: number;
                sort?: string;
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_task_api_v1_projects__projectId__tasks__taskId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                taskId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    node_attempts_api_v1_projects__projectId__tasks__taskId__node_attempts_get: {
        parameters: {
            query?: {
                page?: number;
                pageSize?: number;
            };
            header?: never;
            path: {
                projectId: string;
                taskId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NodeAttemptPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logs_api_v1_projects__projectId__tasks__taskId__logs_get: {
        parameters: {
            query?: {
                afterSequence?: number;
                level?: ("debug" | "info" | "warning" | "error") | null;
                nodeId?: string | null;
                query?: string | null;
                pageSize?: number;
            };
            header?: never;
            path: {
                projectId: string;
                taskId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunLogPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    outputs_api_v1_projects__projectId__tasks__taskId__outputs_get: {
        parameters: {
            query?: {
                page?: number;
                pageSize?: number;
            };
            header?: never;
            path: {
                projectId: string;
                taskId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOutputPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    artifacts_api_v1_projects__projectId__tasks__taskId__artifacts_get: {
        parameters: {
            query?: {
                page?: number;
                pageSize?: number;
            };
            header?: never;
            path: {
                projectId: string;
                taskId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunArtifactPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    artifact_api_v1_projects__projectId__tasks__taskId__artifacts__artifactId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                taskId: string;
                artifactId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunArtifactView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    artifact_content_api_v1_projects__projectId__tasks__taskId__artifacts__artifactId__content_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                taskId: string;
                artifactId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_events_api_v1_projects__projectId__tasks__taskId__events_get: {
        parameters: {
            query?: {
                afterSequence?: number;
            };
            header?: never;
            path: {
                projectId: string;
                taskId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectRunEventPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stream_events_api_v1_projects__projectId__tasks__taskId__events_stream_get: {
        parameters: {
            query?: {
                afterSequence?: number;
            };
            header?: {
                "Last-Event-ID"?: string | null;
            };
            path: {
                projectId: string;
                taskId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_automations_api_v1_projects__projectId__automations_get: {
        parameters: {
            query?: {
                q?: string | null;
                page?: number;
                pageSize?: number;
                sort?: string;
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    create_automation_api_v1_projects__projectId__automations_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AutomationWrite"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationView"];
                };
            };
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_automation_api_v1_projects__projectId__automations__automationId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                automationId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    update_automation_api_v1_projects__projectId__automations__automationId__put: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                automationId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AutomationUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    delete_automation_api_v1_projects__projectId__automations__automationId__delete: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                automationId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AutomationDeleteRequest"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    automation_impact_api_v1_projects__projectId__automations__automationId__impact_get: {
        parameters: {
            query?: {
                action?: "delete" | "unlinkWorkflow";
            };
            header?: never;
            path: {
                projectId: string;
                automationId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationImpactView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    validate_automation_api_v1_projects__projectId__automations__automationId__validation_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                automationId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationValidationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_records_api_v1_projects__projectId__tables__tableId__records_get: {
        parameters: {
            query: {
                datasetGeneration: string;
                filter?: string;
                orderBy?: string;
                page?: number;
                pageSize?: number;
            };
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataRecordPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    create_api_v1_projects__projectId__tables__tableId__records_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataRecordCreate"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataRecordView"];
                };
            };
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataRecordView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    create_batch_api_v1_projects__projectId__tables__tableId__records_batch_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataRecordBatchCreate"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataRecordBatchResponse"];
                };
            };
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataRecordBatchResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_api_v1_projects__projectId__tables__tableId__records__recordKey__get: {
        parameters: {
            query: {
                datasetGeneration: string;
                recordKeyType: "text" | "integer" | "uuid";
            };
            header?: never;
            path: {
                projectId: string;
                tableId: string;
                recordKey: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataRecordView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    delete_record_api_v1_projects__projectId__tables__tableId__records__recordKey__delete: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
                recordKey: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecordDelete"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    update_api_v1_projects__projectId__tables__tableId__records__recordKey__patch: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
                recordKey: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataRecordPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataRecordView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    status_api_v1_projects__projectId__tables__tableId__records__recordKey__status_put: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
                recordKey: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataRecordStatusWrite"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataRecordView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_tables_api_v1_projects__projectId__tables_get: {
        parameters: {
            query?: {
                q?: string | null;
                sourceKind?: ("local" | "excel" | "sheets" | "unconfigured") | null;
                page?: number;
                pageSize?: number;
                sort?: "name" | "-name" | "updatedAt" | "-updatedAt";
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataTablePage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    create_table_api_v1_projects__projectId__tables_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataTableCreate"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataTableView"];
                };
            };
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataTableView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_table_api_v1_projects__projectId__tables__tableId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataTableView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    update_table_api_v1_projects__projectId__tables__tableId__patch: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataTablePatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataTableView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_fields_api_v1_projects__projectId__tables__tableId__fields_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataFieldDirectory"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    create_field_api_v1_projects__projectId__tables__tableId__fields_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataFieldCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataFieldMutationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_statuses_api_v1_projects__projectId__tables__tableId__statuses_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataStatusDirectory"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    create_status_api_v1_projects__projectId__tables__tableId__statuses_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataStatusCreate"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataStatusView"];
                };
            };
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataStatusView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    status_usage_api_v1_projects__projectId__tables__tableId__statuses_usage_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataStatusUsageDirectory"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    delete_status_api_v1_projects__projectId__tables__tableId__statuses__statusId__delete: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
                statusId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatusDelete"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    update_status_api_v1_projects__projectId__tables__tableId__statuses__statusId__patch: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
                statusId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataStatusPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataStatusView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    update_field_api_v1_projects__projectId__tables__tableId__fields__fieldId__patch: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
                fieldId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataFieldPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataFieldMutationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    preview_api_v1_projects__projectId__mutation_impact_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FieldImpactRequest"] | components["schemas"]["StatusDeleteImpactRequest"] | components["schemas"]["RecordDeleteImpactRequest"] | components["schemas"]["SheetsDisconnectImpactRequest"] | components["schemas"]["SheetsBindingImpactRequest"] | components["schemas"]["SheetsUnbindImpactRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FieldImpactReport"] | components["schemas"]["DeletionImpactReport"] | components["schemas"]["SheetsImpactReport"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    preview_api_v1_projects__projectId__tables__tableId__schema_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataSchemaCandidate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataSchemaImpact"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    commit_api_v1_projects__projectId__tables__tableId__schema_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataSchemaCommit"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DataSchemaResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    preview_api_v1_projects__projectId__tables__tableId__record_status_batches_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecordStatusBatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecordStatusBatchPreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    start_api_v1_projects__projectId__tables__tableId__record_status_batches_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecordStatusBatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    cancel_api_v1_projects__projectId__tables__tableId__record_status_batches__operationId__cancel_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
                operationId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecordStatusBatchCancel"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    export_api_v1_projects__projectId__tables__tableId__exports_xlsx_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "x-autoflow-file-window-id": number;
                "x-autoflow-file-window-token": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExcelExportCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    reconcile_api_v1_projects__projectId__operations__operationId__reconcile_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                operationId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReconcileOperationCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_api_v1_projects__projectId__table_imports_excel_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "x-autoflow-file-window-id": number;
                "x-autoflow-file-window-token": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExcelTableImportCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    impact_api_v1_projects__projectId__tables__tableId__imports_excel_impact_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExcelReplaceImpact"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    replace_api_v1_projects__projectId__tables__tableId__imports_excel_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "x-autoflow-file-window-id": number;
                "x-autoflow-file-window-token": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExcelTableReplace"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    inspect_api_v1_projects__projectId__table_imports_excel_inspect_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "x-autoflow-file-window-id": number;
                "x-autoflow-file-window-token": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExcelInspectionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExcelInspectionResult"] | components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Accepted */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_environments_api_v1_projects__projectId__environments_get: {
        parameters: {
            query?: {
                state?: string | null;
                q?: string | null;
                page?: number;
                pageSize?: number;
                sort?: string;
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_environment_api_v1_projects__projectId__environments__environmentId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                environmentId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentDetailView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    delete_environment_api_v1_projects__projectId__environments__environmentId__delete: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                environmentId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnvironmentDeleteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    patch_environment_api_v1_projects__projectId__environments__environmentId__patch: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                environmentId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnvironmentPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    environment_impact_api_v1_projects__projectId__environments__environmentId__impact_get: {
        parameters: {
            query?: {
                action?: string;
            };
            header?: never;
            path: {
                projectId: string;
                environmentId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentImpactView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_instances_api_v1_projects__projectId__environment_instances_get: {
        parameters: {
            query?: {
                state?: string | null;
                taskId?: string | null;
                page?: number;
                pageSize?: number;
                sort?: string;
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentInstancePage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_instance_api_v1_projects__projectId__environment_instances__instanceId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                instanceId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentInstanceView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    open_instance_api_v1_projects__projectId__environment_instances__instanceId__open_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                instanceId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnvironmentOpenRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    save_environment_api_v1_projects__projectId__environment_saves_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnvironmentSaveRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    end_task_api_v1_projects__projectId__tasks__taskId__end_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                taskId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnvironmentEndRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    start_maintenance_api_v1_projects__projectId__environments__environmentId__maintenance_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                environmentId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaintenanceStartRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Locked */
            423: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    discard_maintenance_api_v1_projects__projectId__environments__environmentId__maintenance_discard_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                environmentId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaintenanceDiscardRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    repair_end_api_v1_projects__projectId__environment_operations__operationId__repair_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                operationId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnvironmentRepairRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_environment_operation_api_v1_projects__projectId__environment_operations__operationId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                operationId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_manual_items_api_v1_projects__projectId__manual_items_get: {
        parameters: {
            query?: {
                status?: string | null;
                q?: string | null;
                sort?: "-updatedAt" | "expiresAt";
                page?: number;
                pageSize?: number;
            };
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ManualItemPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    get_manual_item_api_v1_projects__projectId__manual_items__manualItemId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                manualItemId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ManualItemView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    resume_manual_item_api_v1_projects__projectId__manual_items__manualItemId__resume_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                manualItemId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ManualResumeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    finish_manual_item_api_v1_projects__projectId__manual_items__manualItemId__finish_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                manualItemId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ManualFinishRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentOperationView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_connections_api_v1_projects__projectId__sheets_connections_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SheetsConnectionDirectory"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    create_connection_api_v1_projects__projectId__sheets_connections_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SheetsConnectionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    delete_connection_api_v1_projects__projectId__sheets_connections__connectionId__delete: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                connectionId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SheetsConnectionDelete"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    inspect_api_v1_projects__projectId__tables__tableId__sheets_inspect_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SheetsInspectionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SheetsInspectionResult"] | components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Accepted */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_binding_api_v1_projects__projectId__tables__tableId__sheets_binding_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SheetsBinding"] | null;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    put_binding_api_v1_projects__projectId__tables__tableId__sheets_binding_put: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SheetsBindingWrite"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    delete_binding_api_v1_projects__projectId__tables__tableId__sheets_binding_delete: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SheetsBindingDelete"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    sync_state_api_v1_projects__projectId__tables__tableId__sync_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SyncStateView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    pull_api_v1_projects__projectId__tables__tableId__sync_pull_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SyncPullRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    push_api_v1_projects__projectId__tables__tableId__sync_push_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SyncPushRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    pause_api_v1_projects__projectId__tables__tableId__sync_pause_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SyncPauseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SyncStateView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    resume_api_v1_projects__projectId__tables__tableId__sync_resume_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SyncPauseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SyncStateView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    list_operations_api_v1_projects__projectId__tables__tableId__sync_operations_get: {
        parameters: {
            query?: {
                status?: ("pending" | "sending" | "verifying" | "confirmed" | "failed" | "unknown" | "paused") | null;
                page?: number;
                pageSize?: number;
            };
            header?: never;
            path: {
                projectId: string;
                tableId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SyncOperationPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    read_operation_api_v1_projects__projectId__tables__tableId__sync_operations__syncOperationId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                projectId: string;
                tableId: string;
                syncOperationId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SyncOperation"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    reconcile_api_v1_projects__projectId__tables__tableId__sync_operations__syncOperationId__reconcile_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
                syncOperationId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SyncStatusRevisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    abandon_api_v1_projects__projectId__tables__tableId__sync_operations__syncOperationId__abandon_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                projectId: string;
                tableId: string;
                syncOperationId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SyncAbandonRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SyncOperation"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Precondition Failed */
            412: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BrowserErrorEnvelope"];
                };
            };
        };
    };
    execute_workflow_api_workflows__workflow_id__execute_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workflow_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkflowExecuteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stop_workflow_api_workflows__workflow_id__stop_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workflow_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkflowStopRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_workflows_api_workflows_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
        };
    };
    create_workflow_api_workflows_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkflowWrite"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    latest_data_api_workflows_data_latest_full_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    global_variables_api_workflows_global_variables_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    get_workflow_api_workflows__workflow_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workflow_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_workflow_api_workflows__workflow_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workflow_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkflowUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_workflow_api_workflows__workflow_id__delete: {
        parameters: {
            query: {
                expectedRevision: number;
            };
            header?: never;
            path: {
                workflow_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_results_api_workflow_runs__run_id__results_get: {
        parameters: {
            query?: {
                cursor?: number;
                limit?: number;
                throughSequence?: number | null;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StudioRunResultPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_result_value_api_workflow_runs__run_id__results__sequence__value_get: {
        parameters: {
            query: {
                key: string;
            };
            header?: never;
            path: {
                run_id: string;
                sequence: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StudioRunResultValue"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_results_api_workflow_runs__run_id__results_export_get: {
        parameters: {
            query: {
                throughSequence: number;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_artifacts_api_workflow_runs__run_id__artifacts_get: {
        parameters: {
            query?: {
                cursor?: number;
                limit?: number;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_artifact_api_workflow_runs__run_id__artifacts__artifact_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
                artifact_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_runs_api_workflow_runs_get: {
        parameters: {
            query?: {
                documentId?: string | null;
                cursor?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_run_api_workflow_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_logs_api_workflow_runs__run_id__logs_get: {
        parameters: {
            query?: {
                cursor?: number;
                limit?: number;
                query?: string | null;
                levels?: string | null;
                nodeId?: string | null;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stream_events_api_events_stream_get: {
        parameters: {
            query?: {
                afterSeq?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_command_api_events_commands_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StudioEventCommandRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StudioCommandReceipt"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_command_api_events_commands__command_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                command_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StudioCommandLookup"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_input_prompt_api_events_input_prompts__request_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StudioInputPromptState"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    environment_api_v1_android_environment_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AndroidEnvironment"];
                };
            };
        };
    };
    devices_api_v1_android_devices_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AndroidDeviceRead"][];
                };
            };
        };
    };
    create_api_v1_android_devices_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AndroidCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AndroidDeviceRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    operation_api_v1_android_devices__device_id__operations_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                device_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AndroidDeviceCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AndroidDeviceRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_api_v1_android_devices__device_id__preview_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                device_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    device_api_v1_android_devices__device_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                device_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AndroidDeviceRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rename_api_v1_android_devices__device_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                device_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AndroidRename"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AndroidDeviceRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    profiles_api_v1_android_profiles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentProfile"][];
                };
            };
        };
    };
    save_profile_api_v1_android_profiles__identifier__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnvironmentProfile"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnvironmentProfile"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    batches_api_v1_android_batches_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BatchRead"][];
                };
            };
        };
    };
    batch_api_v1_android_batches_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BatchCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BatchRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    batch_action_api_v1_android_batches__identifier__actions_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BatchAction"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BatchRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    allocations_api_v1_android_allocations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AllocationRead"][];
                };
            };
        };
    };
    allocate_api_v1_android_allocations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AllocationCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AllocationRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_allocation_api_v1_android_allocations__identifier__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AllocationRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    history_api_v1_android_devices__identifier__runs_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
            };
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeviceRunRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    session_api_v1_android_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_session_api_v1_android_sessions__identifier__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    action_api_v1_android_sessions__identifier__actions_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionAction"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    command_api_v1_android_sessions__identifier__input_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ControlCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stream_api_v1_android_sessions__identifier__stream_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    apps_api_v1_android_sessions__identifier__apps_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AppInfo"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    launch_api_v1_android_sessions__identifier__apps_launch_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AppLaunch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    install_api_v1_android_sessions__identifier__apps_install_post: {
        parameters: {
            query: {
                generation: number;
            };
            header?: never;
            path: {
                identifier: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": {
                    /** Format: binary */
                    file: string;
                };
                "application/vnd.android.package-archive": string;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
