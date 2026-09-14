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
        delete?: never;
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
            resource: components["schemas"]["FieldResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["StatusResourceLocator"];
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
            resource: components["schemas"]["FieldResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["StatusResourceLocator"];
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
        /** EmptyCommand */
        EmptyCommand: Record<string, never>;
        /** Endpoint */
        Endpoint: {
            /** Host */
            host: string;
            /** Port */
            port: number;
        };
        /** EnvironmentOptionRead */
        EnvironmentOptionRead: {
            /** Value */
            value: string;
            /** Label */
            label: string;
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
        /** ProjectCapabilities */
        ProjectCapabilities: {
            /**
             * Automations
             * @constant
             */
            automations: "notImplemented";
            /**
             * Data
             * @constant
             */
            data: "available";
            /**
             * Runs
             * @constant
             */
            runs: "notImplemented";
            /**
             * Environments
             * @constant
             */
            environments: "notImplemented";
            /**
             * Statistics
             * @constant
             */
            statistics: "notImplemented";
            /**
             * Sync
             * @constant
             */
            sync: "notImplemented";
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
            kind: "createProject" | "updateProject" | "createTable" | "updateTable" | "mutateField" | "saveTableSchema" | "mutateStatus" | "createRecord" | "createRecords" | "updateRecord" | "setRecordStatus" | "deleteRecord" | "setRecordStatuses" | "cancelRecordStatuses" | "inspectExcel" | "importExcel" | "exportXlsx" | "reconcileOperation";
            /**
             * Status
             * @enum {string}
             */
            status: "accepted" | "running" | "reconciling" | "succeeded" | "failed";
            /** Statusrevision */
            statusRevision: number;
            /** Resource */
            resource: components["schemas"]["ProjectResourceLocator"] | components["schemas"]["TableResourceLocator"] | components["schemas"]["FieldResourceLocator"] | components["schemas"]["StatusResourceLocator"] | components["schemas"]["RecordResourceLocator"];
            /** Result */
            result: components["schemas"]["ProjectView"] | components["schemas"]["DataTableView"] | components["schemas"]["FieldMutationResult"] | components["schemas"]["DataSchemaResult"] | components["schemas"]["StatusMutationResult"] | components["schemas"]["StatusDeleteResult"] | components["schemas"]["DataRecordView"] | components["schemas"]["DataRecordBatchResult"] | components["schemas"]["RecordDeleteResult"] | components["schemas"]["RecordStatusBatchOutcome"] | components["schemas"]["ExcelInspectionView"] | components["schemas"]["ExcelImportResult"] | components["schemas"]["ExcelExportResult"] | components["schemas"]["ExcelReconcileResult"] | components["schemas"]["CancelRecordStatusesResult"] | null;
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
            activity: {
                [key: string]: unknown;
            }[];
            /** Recent */
            recent: {
                [key: string]: unknown;
            }[];
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
        /** RecordStatusBatchBlocker */
        RecordStatusBatchBlocker: {
            /** Code */
            code: string;
            /** Resource */
            resource: components["schemas"]["FieldResourceLocator"] | components["schemas"]["RecordResourceLocator"] | components["schemas"]["StatusResourceLocator"];
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
        /** SourceDefaultProxy */
        SourceDefaultProxy: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "sourceDefault";
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
        /** StudioRequestClaim */
        StudioRequestClaim: {
            /** Requestid */
            requestId: string;
            /** Claimid */
            claimId: string;
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
                kind?: ("createProject" | "updateProject" | "createTable" | "updateTable" | "mutateField" | "saveTableSchema" | "mutateStatus" | "createRecord" | "createRecords" | "updateRecord" | "setRecordStatus" | "deleteRecord" | "setRecordStatuses" | "cancelRecordStatuses" | "inspectExcel" | "importExcel" | "exportXlsx" | "reconcileOperation") | null;
                status?: ("accepted" | "running" | "reconciling" | "succeeded" | "failed") | null;
                resourceType?: ("project" | "table" | "field" | "status" | "record") | null;
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
                "application/json": components["schemas"]["FieldImpactRequest"] | components["schemas"]["StatusDeleteImpactRequest"] | components["schemas"]["RecordDeleteImpactRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FieldImpactReport"] | components["schemas"]["DeletionImpactReport"];
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
}
