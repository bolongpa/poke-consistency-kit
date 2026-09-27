"""poke-consistency-kit: Gen-1 Pokemon ontology + visual-consistency toolkit."""
from .graph import PokeGraph
from .prompt_builder import build_prompt
from .verifier import FakeVLM, OpenAICompatibleVLM, VerificationReport

__all__ = ["PokeGraph", "build_prompt", "FakeVLM", "OpenAICompatibleVLM",
           "VerificationReport"]
__version__ = "1.0.0"
