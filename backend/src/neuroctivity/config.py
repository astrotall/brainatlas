from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore", frozen=True)

    api_docs_enabled: bool = False
    vercel: str = ""

    @property
    def serves_api_docs(self) -> bool:
        return self.api_docs_enabled and not self.vercel
