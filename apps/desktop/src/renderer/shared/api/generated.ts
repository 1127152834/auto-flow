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
    "/api/v1/proxies/{projection_id}/change-ip": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Unavailable Change Ip */
        post: operations["unavailable_change_ip_api_v1_proxies__projection_id__change_ip_post"];
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
        /** Unavailable Relocate */
        post: operations["unavailable_relocate_api_v1_proxies__projection_id__relocate_post"];
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
        /** Unavailable Get Rotation */
        get: operations["unavailable_get_rotation_api_v1_proxies__projection_id__rotation_schedule_get"];
        /** Unavailable Set Rotation */
        put: operations["unavailable_set_rotation_api_v1_proxies__projection_id__rotation_schedule_put"];
        post?: never;
        /** Unavailable Delete Rotation */
        delete: operations["unavailable_delete_rotation_api_v1_proxies__projection_id__rotation_schedule_delete"];
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
        /** Unavailable Credentials */
        get: operations["unavailable_credentials_api_v1_proxies__projection_id__credentials_get"];
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
    "/api/v1/proxy-panel/connections/{connection_id}/locations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Unavailable Locations */
        get: operations["unavailable_locations_api_v1_proxy_panel_connections__connection_id__locations_get"];
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
        /** ActionResult[ProxyView] */
        ActionResult_ProxyView_: {
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "accepted" | "failed";
            /** Operation Id */
            operation_id?: string | null;
            resource?: components["schemas"]["ProxyView"] | null;
            error?: components["schemas"]["ApiError"] | null;
        };
        /** ActionResult[RotationSchedule] */
        ActionResult_RotationSchedule_: {
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "accepted" | "failed";
            /** Operation Id */
            operation_id?: string | null;
            resource?: components["schemas"]["RotationSchedule"] | null;
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
        /** EmptyCommand */
        EmptyCommand: Record<string, never>;
        /** Endpoint */
        Endpoint: {
            /** Host */
            host: string;
            /** Port */
            port: number;
        };
        /** ErrorResponse */
        ErrorResponse: {
            error: components["schemas"]["ApiError"];
        };
        /** ExpectedRevision */
        ExpectedRevision: {
            /** Expected Revision */
            expected_revision: number;
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
        /** PoolOption */
        PoolOption: {
            /** Id */
            id: string;
            /** Name */
            name: string;
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
            mode?: ("same_city" | "random_city" | "same_carrier") | null;
            /** Interval Seconds */
            interval_seconds?: number | null;
        };
        /** RotationScheduleUpdate */
        RotationScheduleUpdate: {
            /** Expected Revision */
            expected_revision: number;
            /**
             * Mode
             * @enum {string}
             */
            mode: "same_city" | "random_city" | "same_carrier";
            /** Interval Seconds */
            interval_seconds: number;
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
        /** ActionResult */
        ActionResult: {
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "accepted" | "failed";
            /**
             * Operation Id
             * @default null
             */
            operation_id: string | null;
            /**
             * Resource
             * @default null
             */
            resource: unknown | null;
            /** @default null */
            error: components["schemas"]["ApiError"] | null;
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
            /**
             * Resource Revision
             * @default null
             */
            resource_revision: number | null;
            /** @default null */
            error: components["schemas"]["ApiError"] | null;
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
    unavailable_change_ip_api_v1_proxies__projection_id__change_ip_post: {
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
                    "application/json": components["schemas"]["ActionResult_ProxyView_"];
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
    unavailable_relocate_api_v1_proxies__projection_id__relocate_post: {
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
                "application/json": components["schemas"]["RelocateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult_ProxyView_"];
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
    unavailable_get_rotation_api_v1_proxies__projection_id__rotation_schedule_get: {
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
    unavailable_set_rotation_api_v1_proxies__projection_id__rotation_schedule_put: {
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
                "application/json": components["schemas"]["RotationScheduleUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResult_RotationSchedule_"];
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
    unavailable_delete_rotation_api_v1_proxies__projection_id__rotation_schedule_delete: {
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
                    "application/json": components["schemas"]["ActionResult_RotationSchedule_"];
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
    unavailable_credentials_api_v1_proxies__projection_id__credentials_get: {
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
    unavailable_locations_api_v1_proxy_panel_connections__connection_id__locations_get: {
        parameters: {
            query?: {
                q?: string | null;
                carrier?: string | null;
                refresh?: boolean;
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
}
