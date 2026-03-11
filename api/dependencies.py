"""Singleton agent + data service for FastAPI dependency injection."""

import logging

from core.agent import Agent
from core.llm_client import LLMClient
from data.loader import DataBundle, load_from_local
from config.settings import settings

logger = logging.getLogger(__name__)

_bundle: DataBundle | None = None
_agent: Agent | None = None
_llm_client = None
_chroma_store = None

async def init_services():
    """
    Called once at startup. Initialize all services in order:
    1. Data loader (reads CSVs into memory)
    2. ChromaDB store (connect or create collection)
    3. LLM client (verify API keys, test connectivity)
    4. Agent pipeline (wires everything together)
    """
    global _bundle, _agent, _llm_client, _chroma_store
 # 2. ChromaDB
    # from knowledge.chroma_store import ChromaStore
    # _chroma_store = ChromaStore()
    # await _chroma_store.connect()
    logger.info("ChromaDB store initialized (placeholder)")
    logger.info(f"LLM providers available: {llm.available_providers}")
    
    # 1. Data loader
    # from data.loader import DataLoader
    # _data_loader = DataLoader()
    # await _data_loader.load()
    logger.info("Loading dataset from %s", settings.data_dir)
    _bundle = load_from_local()


    # 3. LLM Client
    # from core.llm_client import LLMClient
    # _llm_client = LLMClient()
    # await _llm_client.health_check()
    logger.info("LLM client initialized (placeholder)")
    llm = LLMClient()
 # 4. Agent
    # from core.agent import BriefMDAgent
    # _agent = BriefMDAgent(
    #     data_loader=_data_loader,
    #     llm_client=_llm_client,
    #     chroma_store=_chroma_store,
    # )

    logger.info("Initializing agent pipeline")
    _agent = Agent(
        llm_client=llm,
        all_diagnoses=_bundle.diagnoses,
        diagnosis_dict=_bundle.diagnosis_dict,
    )

    logger.info("Services initialized")


async def shutdown_services():
    global _bundle, _agent, _llm_client, _chroma_store
    
    _bundle = None
    _agent = None
    _llm_client = None
    _chroma_store = None
    logger.info("Services shut down")


def get_bundle() -> DataBundle:
    if _bundle is None:
        raise RuntimeError("Data not loaded. Call init_services() first.")
    return _bundle


def get_agent() -> Agent:
    if _agent is None:
        raise RuntimeError("Agent not initialized. Call init_services() first.")
    return _agent

def get_llm_client():
    if _llm_client is None:
        raise RuntimeError("LLM client not initialized.")
    return _llm_client


def get_chroma_store():
    if _chroma_store is None:
        raise RuntimeError("ChromaDB store not initialized.")
    return _chroma_store


