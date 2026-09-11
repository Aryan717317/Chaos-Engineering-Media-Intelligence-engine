"""External crawl configuration and URL boundaries."""

import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Only absolute http(s) URLs are supported")
    if parts.username or parts.password:
        raise ValueError("URLs must not contain credentials")
    host = parts.hostname.lower().rstrip(".").encode("idna").decode()
    port = parts.port
    if ":" in host:
        host = f"[{host}]"
    if port and (parts.scheme.lower(), port) not in {("https", 443), ("http", 80)}:
        host += f":{port}"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(sorted(query)), ""))


def domain_allowed(url: str, domains: list[str]) -> bool:
    try:
        host = urlsplit(canonical_url(url)).hostname
    except ValueError:
        return False
    return any(host == domain or host.endswith("." + domain) for domain in domains)


class SourceRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: str = "web"
    body_selector: str | None = None
    comment_selector: str | None = None
    title_selector: str | None = None
    follow_pattern: str | None = None

    @field_validator("follow_pattern")
    @classmethod
    def valid_pattern(cls, value: str | None) -> str | None:
        if value:
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError(f"Invalid follow_pattern: {exc}") from exc
        return value


class Seed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    source_type: str | None = None

    @field_validator("url")
    @classmethod
    def clean_url(cls, value: str) -> str:
        return canonical_url(value)


class CrawlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seeds: list[Seed] = Field(min_length=1)
    allowed_domains: list[str] = Field(min_length=1)
    max_depth: int = Field(default=1, ge=0, le=5)
    max_pages: int = Field(default=12, ge=1, le=500)
    max_links_per_page: int = Field(default=2, ge=0, le=100)
    delay_seconds: float = Field(default=1.0, ge=0, le=60)
    page_timeout_ms: int = Field(default=30000, ge=1000, le=120000)
    source_rules: dict[str, SourceRule] = Field(default_factory=dict)

    @field_validator("seeds", mode="before")
    @classmethod
    def accept_plain_urls(cls, value: list) -> list:
        return [{"url": seed} if isinstance(seed, str) else seed for seed in value]

    @field_validator("allowed_domains")
    @classmethod
    def validate_domains(cls, values: list[str]) -> list[str]:
        domains = [value.lower().strip().rstrip(".") for value in values]
        if any(not re.fullmatch(r"[a-z0-9]+(?:[a-z0-9.-]*[a-z0-9])?", d) for d in domains):
            raise ValueError("Whitelist entries must be bare domain names, without paths or ports")
        return sorted(set(domains))

    @model_validator(mode="after")
    def check_seeds(self):
        if any(not domain_allowed(seed.url, self.allowed_domains) for seed in self.seeds):
            raise ValueError("Every seed must be inside allowed_domains")
        if len({s.url for s in self.seeds}) > self.max_pages:
            raise ValueError("max_pages must accommodate all distinct seeds")
        return self

    def rule_for(self, url: str) -> SourceRule:
        for domain in sorted(self.source_rules, key=len, reverse=True):
            if domain_allowed(url, [domain]):
                return self.source_rules[domain]
        return SourceRule()


def load_config(path: str | Path) -> CrawlConfig:
    with Path(path).open(encoding="utf-8") as stream:
        return CrawlConfig.model_validate(yaml.safe_load(stream))
