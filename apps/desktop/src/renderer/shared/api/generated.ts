export type paths = {
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
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
};
export type $defs = Record<string, never>;
export interface operations {
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
