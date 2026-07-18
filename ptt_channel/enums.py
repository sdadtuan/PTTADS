"""Enums for multi-channel adapter layer."""
from __future__ import annotations

from enum import Enum


class ChannelCode(str, Enum):
    META = "meta"
    ZALO = "zalo"
    GOOGLE = "google"
    EMAIL = "email"
    TIKTOK = "tiktok"


class AssetType(str, Enum):
    AD_ACCOUNT = "ad_account"
    BUSINESS_MANAGER = "business_manager"
    PAGE = "page"
    PIXEL = "pixel"
    DATASET = "dataset"
    OA = "oa"
    ZNS_TEMPLATE = "zns_template"
    MCC = "mcc"
    CONVERSION_ACTION = "conversion_action"
    ESP_DOMAIN = "esp_domain"
    ESP_LIST = "esp_list"


class StandardEventName(str, Enum):
    PAGE_VIEW = "page_view"
    VIEW_CONTENT = "view_content"
    LEAD = "lead"
    COMPLETE_REGISTRATION = "complete_registration"
    CONTACT = "contact"
    ADD_TO_CART = "add_to_cart"
    INITIATE_CHECKOUT = "initiate_checkout"
    PURCHASE = "purchase"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    EMAIL_OPEN = "email_open"
    EMAIL_CLICK = "email_click"


class SyncJobType(str, Enum):
    FULL_ACCOUNT = "full_account"
    CAMPAIGNS = "campaigns"
    ADSETS = "adsets"
    ADS = "ads"
    INSIGHTS_DAILY = "insights_daily"
    LEADS_DELTA = "leads_delta"
    ASSETS = "assets"
    EMAIL_STATS = "email_stats"


class CampaignObjective(str, Enum):
    LEADS = "leads"
    TRAFFIC = "traffic"
    SALES = "sales"
    AWARENESS = "awareness"
    ENGAGEMENT = "engagement"


class EventSource(str, Enum):
    BROWSER = "browser"
    SERVER = "server"
    WEBHOOK = "webhook"
    CRM = "crm"
    EMAIL = "email"
