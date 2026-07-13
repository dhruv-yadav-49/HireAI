from app.models.enums import ProviderType
from app.services.providers.base_provider import CommunicationProvider
from app.services.providers import (
    MockProvider,
    SMTPProvider,
    GmailProvider,
    SESProvider,
    MetaWhatsAppProvider,
    TwilioWhatsAppProvider,
    TwilioSMSProvider,
    Msg91SMSProvider,
)

# Registry mapping ProviderType to concrete provider implementations
PROVIDERS: dict[ProviderType, CommunicationProvider] = {
    ProviderType.SMTP: SMTPProvider(),
    ProviderType.GMAIL: GmailProvider(),
    ProviderType.SES: SESProvider(),
    ProviderType.META: MetaWhatsAppProvider(),
    ProviderType.TWILIO: TwilioWhatsAppProvider(), # Twilio provider in registry used for WhatsApp
    # Note: Twilio is also used for SMS. We can have twilio resolve to either SMS or WhatsApp based on registry usage or we can map them dynamically.
    # To support this dynamically, we can inspect ProviderType.TWILIO and returning either TwilioWhatsAppProvider or TwilioSMSProvider based on channel.
    ProviderType.MSG91: Msg91SMSProvider(),
    ProviderType.MOCK: MockProvider(),
}


class ProviderRegistry:
    """Registry engine resolver for communication providers."""

    @staticmethod
    def get_provider(provider_type: ProviderType, channel: str) -> CommunicationProvider:
        """Resolves the appropriate concrete provider based on its type and channel."""
        # Special routing for Twilio based on channel (WhatsApp vs SMS)
        if provider_type == ProviderType.TWILIO:
            if channel.upper() == "WHATSAPP":
                return TwilioWhatsAppProvider()
            else:
                return TwilioSMSProvider()
                
        provider = PROVIDERS.get(provider_type)
        if provider is None:
            raise ValueError(f"No provider implementation registered for provider type: {provider_type}")
        return provider
