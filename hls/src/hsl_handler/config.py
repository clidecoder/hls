"""Configuration management for the webhook handler."""

import os
import yaml
from typing import Dict, List, Optional, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    """Server configuration."""
    model_config = SettingsConfigDict(extra="ignore")
    host: str = "0.0.0.0"
    port: int = 9000
    webhook_path: str = "/github-webhook"


class GitHubConfig(BaseSettings):
    """GitHub API configuration."""
    model_config = SettingsConfigDict(extra="ignore")
    token: str = Field(default="", env="GITHUB_TOKEN")
    webhook_secret: str = Field(default="", env="GITHUB_WEBHOOK_SECRET")


class ClaudeConfig(BaseSettings):
    """Claude Code configuration."""
    model_config = SettingsConfigDict(extra="ignore")
    api_key: str = Field(default="claude-code", env="ANTHROPIC_API_KEY")  # Default to indicate Claude Code usage
    model: str = "claude-3-sonnet-20240229"
    max_tokens: int = 4000


class RepositoryConfig(BaseSettings):
    """Repository-specific configuration."""
    model_config = SettingsConfigDict(extra="ignore")
    name: str
    enabled: bool = True
    local_path: Optional[str] = None
    events: List[str]
    settings: Dict[str, Any] = {}


class PromptsConfig(BaseSettings):
    """Prompts configuration."""
    model_config = SettingsConfigDict(extra="ignore")
    base_dir: str = "./prompts"
    templates: Dict[str, Dict[str, str]] = {}


class OutputsConfig(BaseSettings):
    """Output directories configuration."""
    model_config = SettingsConfigDict(extra="ignore")
    base_dir: str = "./outputs"
    directories: Dict[str, str] = {}


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    model_config = SettingsConfigDict(extra="ignore")
    level: str = "INFO"
    format: str = "json"
    file: str = "./logs/webhook.log"
    max_size_mb: int = 10
    backup_count: int = 5


class FeaturesConfig(BaseSettings):
    """Feature flags configuration."""
    model_config = SettingsConfigDict(extra="ignore")
    async_processing: bool = True
    rate_limiting: bool = True
    signature_validation: bool = True
    payload_logging: bool = False


class CronAnalysisConfig(BaseSettings):
    """Cron job configuration for analyzing missed issues."""
    model_config = SettingsConfigDict(extra="ignore")
    enabled: bool = True
    min_age_minutes: int = 30
    max_issues_per_repo: int = 10
    delay_between_issues: int = 2
    analyzed_label: str = "clide-analyzed"
    log_level: str = "INFO"


class InvitationCriteriaConfig(BaseSettings):
    """Criteria for auto-accepting invitations."""
    model_config = SettingsConfigDict(extra="ignore")
    repository_patterns: List[str] = ["*"]
    from_organizations: Optional[List[str]] = None
    from_users: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None


class PostAcceptanceConfig(BaseSettings):
    """Configuration for post-acceptance actions."""
    model_config = SettingsConfigDict(extra="ignore")
    clone_repository: bool = True
    clone_base_dir: str = "/home/clide"
    update_config: bool = True
    register_webhook: bool = True
    webhook_url: str = "https://clidecoder.com/hooks/github-webhook"
    webhook_events: List[str] = ["issues", "pull_request", "pull_request_review"]


class AutoAcceptInvitationsConfig(BaseSettings):
    """Configuration for automatically accepting repository invitations."""
    model_config = SettingsConfigDict(extra="ignore")
    enabled: bool = True
    check_interval_minutes: int = 10
    log_level: str = "INFO"
    criteria: InvitationCriteriaConfig = InvitationCriteriaConfig()
    post_acceptance: PostAcceptanceConfig = PostAcceptanceConfig()


class Settings(BaseSettings):
    """Main settings class."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    server: ServerConfig = ServerConfig()
    github: GitHubConfig = GitHubConfig()
    claude: ClaudeConfig = ClaudeConfig()
    repositories: List[RepositoryConfig] = []
    prompts: PromptsConfig = PromptsConfig()
    outputs: OutputsConfig = OutputsConfig()
    logging: LoggingConfig = LoggingConfig()
    features: FeaturesConfig = FeaturesConfig()
    cron_analysis: CronAnalysisConfig = CronAnalysisConfig()
    auto_accept_invitations: AutoAcceptInvitationsConfig = AutoAcceptInvitationsConfig()

    @classmethod
    def from_yaml(cls, config_path: str) -> "Settings":
        """Load settings from YAML file with environment variable substitution."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Substitute environment variables
        config_data = cls._substitute_env_vars(config_data)
        
        return cls(**config_data)
    
    @staticmethod
    def _substitute_env_vars(obj: Any) -> Any:
        """Recursively substitute environment variables in config."""
        if isinstance(obj, dict):
            return {k: Settings._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [Settings._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]
            return os.getenv(env_var, obj)
        else:
            return obj

    def get_repository_config(self, repo_name: str) -> Optional[RepositoryConfig]:
        """Get configuration for a specific repository."""
        for repo in self.repositories:
            if repo.name == repo_name:
                return repo
        return None

    def is_event_enabled(self, repo_name: str, event_type: str) -> bool:
        """Check if an event type is enabled for a repository."""
        repo_config = self.get_repository_config(repo_name)
        if not repo_config:
            return False
        return event_type in repo_config.events


def load_settings(config_path: Optional[str] = None) -> Settings:
    """Load settings from file or environment."""
    if config_path:
        return Settings.from_yaml(config_path)
    
    # Default config path
    default_path = "config/settings.yaml"
    if os.path.exists(default_path):
        return Settings.from_yaml(default_path)
    
    # Fall back to environment variables only
    return Settings()