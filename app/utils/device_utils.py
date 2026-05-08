import re
from user_agents import parse


def detect_device_info(user_agent_string):
    """Detecta informações completas do dispositivo"""
    ua = parse(user_agent_string)

    # Detectar tipo de dispositivo
    if ua.is_mobile:
        device_type = "mobile"
    elif ua.is_tablet:
        device_type = "tablet"
    elif ua.is_pc:
        device_type = "desktop"
    else:
        device_type = "unknown"

    # Detectar SO
    os_family = ua.os.family
    if "Windows" in os_family:
        os = "Windows"
    elif "Mac" in os_family:
        os = "MacOS"
    elif "Linux" in os_family:
        os = "Linux"
    elif "Android" in os_family:
        os = "Android"
    elif "iOS" in os_family or "iPhone" in os_family or "iPad" in os_family:
        os = "iOS"
    else:
        os = os_family

    return {
        "device_type": device_type,
        "os": os,
        "os_version": ua.os.version,
        "browser": ua.browser.family,
        "browser_version": ua.browser.version_string,
        "is_mobile": ua.is_mobile,
        "is_tablet": ua.is_tablet,
        "is_pc": ua.is_pc,
        "is_bot": ua.is_bot,
        "user_agent": user_agent_string,
    }


def get_client_ip(request):
    """Obtém IP real do cliente considerando proxies"""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    return ip
