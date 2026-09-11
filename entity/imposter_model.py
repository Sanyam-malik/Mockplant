from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class ImposterMetadata:
    """Represents the metadata of an imposter (name, type, description)."""
    name: str
    description: Optional[str] = ""
    type: str = "HTTP"
    file: Optional[str] = ""

@dataclass
class Response:
    """Represents a response configuration."""
    code: int
    content: str
    content_type: Optional[str] = "text/plain"
    headers: Optional[Dict[str, str]] = field(default_factory=dict)

@dataclass
class ResponseEntry:
    """Represents a response entry with conditions."""
    response: Response
    when: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Predicate:
    """Represents a predicate configuration."""
    method: str
    path: str
    delay: Optional[str] = None
    force_response: Optional[int] = None
    responses: List[ResponseEntry] = field(default_factory=list)
    # Multiple workflows for this predicate
    workflows: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Imposter:
    """Represents a complete imposter configuration."""
    imposter: ImposterMetadata
    predicates: List[Predicate] = field(default_factory=list)
