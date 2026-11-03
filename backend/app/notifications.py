import os
def send_sms(phone,message):
    # Provider-specific API integration requires your own account and credentials.
    if os.getenv("SMS_ENABLED","false").lower()!="true":
        return {"sent":False,"mode":"demo","detail":"SMS disabled; live display and browser voice remain available."}
    if not os.getenv("SMS_PROVIDER") or not os.getenv("SMS_API_KEY"):
        return {"sent":False,"mode":"configuration_missing"}
    return {"sent":False,"mode":"adapter_required","detail":"Add the chosen provider's documented API request here."}
