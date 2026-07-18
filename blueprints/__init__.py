"""Register CRM Product Model v1 blueprints."""
from __future__ import annotations

from flask import Flask

# url_for() / redirect() trước P4 dùng endpoint không prefix blueprint.
_LEGACY_ENDPOINT_ALIASES: dict[str, str] = {
    "crm_catalog.crm_catalog_page": "crm_catalog_page",
    "crm_catalog.api_crm_catalog_public": "api_crm_catalog_public",
    "crm_catalog.api_crm_catalog_services_list": "api_crm_catalog_services_list",
    "crm_catalog.api_crm_catalog_services_create": "api_crm_catalog_services_create",
    "crm_catalog.api_crm_catalog_services_update": "api_crm_catalog_services_update",
    "crm_catalog.api_crm_catalog_industries_list": "api_crm_catalog_industries_list",
    "crm_catalog.api_crm_catalog_industries_create": "api_crm_catalog_industries_create",
    "crm_catalog.api_crm_catalog_industries_update": "api_crm_catalog_industries_update",
    "crm_catalog.api_crm_assign_scopes_list": "api_crm_assign_scopes_list",
    "crm_catalog.api_crm_assign_scopes_create": "api_crm_assign_scopes_create",
    "crm_catalog.api_crm_assign_scopes_update": "api_crm_assign_scopes_update",
    "crm_catalog.api_crm_assign_scopes_delete": "api_crm_assign_scopes_delete",
    "crm_leads_product.api_crm_leads_review_queue_sync": "api_crm_leads_review_queue_sync",
    "crm_leads_product.api_crm_lead_review_queue_release": "api_crm_lead_review_queue_release",
    "crm_leads_product.api_crm_lead_industry_addon_get": "api_crm_lead_industry_addon_get",
    "crm_leads_product.api_crm_lead_industry_addon_patch": "api_crm_lead_industry_addon_patch",
    "crm_presales.api_crm_lead_presales_marketing_plan_get": "api_crm_lead_presales_marketing_plan_get",
    "crm_presales.api_crm_lead_presales_marketing_plan_patch": "api_crm_lead_presales_marketing_plan_patch",
    "crm_lifecycle.api_svc_lifecycle_marketing_plan_get": "api_svc_lifecycle_marketing_plan_get",
    "crm_lifecycle.api_svc_lifecycle_marketing_plan_patch": "api_svc_lifecycle_marketing_plan_patch",
}


def _add_legacy_endpoint_aliases(app: Flask) -> None:
    for rule in list(app.url_map.iter_rules()):
        legacy = _LEGACY_ENDPOINT_ALIASES.get(rule.endpoint)
        if not legacy or legacy in app.view_functions:
            continue
        view_func = app.view_functions[rule.endpoint]
        app.add_url_rule(
            rule.rule,
            endpoint=legacy,
            view_func=view_func,
            methods=rule.methods,
        )


def register_crm_product_blueprints(app: Flask) -> None:
    from blueprints.agency import bp as agency_bp
    from blueprints.catalog import bp as catalog_bp
    from blueprints.channel_webhooks import bp as channel_webhooks_bp
    from blueprints.crm_leads_v1 import bp as crm_leads_v1_bp
    from blueprints.leads import bp as leads_bp
    from blueprints.lifecycle import bp as lifecycle_bp
    from blueprints.presales import bp as presales_bp

    for bp in (
        catalog_bp,
        leads_bp,
        presales_bp,
        lifecycle_bp,
        channel_webhooks_bp,
        agency_bp,
        crm_leads_v1_bp,
    ):
        app.register_blueprint(bp)
    _add_legacy_endpoint_aliases(app)
