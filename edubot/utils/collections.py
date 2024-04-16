import logging
import textwrap
from pathlib import Path
import os
import openai
from django.core.files.base import ContentFile
import nest_asyncio
import zipfile

from django.conf import settings
from uuid import UUID
# from langchain import OpenAI
# from llama_index import GPTSimpleVectorIndex, LLMPredictor, ServiceContext
import chromadb
from llama_index.vector_stores.duckdb import DuckDBVectorStore
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext
from llama_index.core import Settings
from chromadb.config import Settings as ChromaSettings

from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.llms.openai import OpenAI
from llama_index.core.query_engine import SubQuestionQueryEngine
from llama_index.agent.openai import OpenAIAgent


from edubot.indexes.models import Collection

logger = logging.getLogger(__name__)

# nest_asyncio.apply()
openai.api_key=settings.OPENAI_API
logger.info(f"OpenAI API Key: {settings.OPENAI_API}")
def format_source(source):
    """
    Format a source object as a nicely-structured markdown text.

    Args:
        source (llama_index.schema.Source): The source object to format.

    Returns:
        str: The formatted markdown text for the given source.
    """
    formatted_source = (
        f"- **{source.title}**\n\n{textwrap.indent(source.content, '  ')}\n\n"
    )
    return formatted_source


def is_pure_zip_file(file_path_or_file_object):
    """
    Checks if the given file path or file object is a ZIP file and not a DOCX file.
    
    Args:
        file_path_or_file_object (str or file-like object): The path to the file or a file-like object to check.
        
    Returns:
        bool: True if the file is a pure ZIP file, False if it is not a ZIP or if it is a DOCX file.
    """
    if zipfile.is_zipfile(file_path_or_file_object):
        with zipfile.ZipFile(file_path_or_file_object, 'r') as zip_obj:
            # Check for DOCX specific file
            if any(name for name in zip_obj.namelist() if name.startswith('word/') or name.endswith('.xml')):
                return False  # This might be a DOCX file or another Office format
        return True  # It's a ZIP file and doesn't appear to be a DOCX file
    else:
        return False  # It's not a ZIP file at all

async def load_collection_model(collection_id: str | int) -> VectorStoreIndex:
    """
    Load the Collection model from cache or the database, and return the index.

    Args:
        collection_id (Union[str, int]): The ID of the Collection model instance.

    Returns:
        VectorStoreIndex: The loaded index.

    This function performs the following steps:
    1. Retrieve the Collection object with the given collection_id.
    2. Check if a JSON file with the name '/cache/model_{collection_id}.json' exists.
    3. If the JSON file doesn't exist, load the JSON from the Collection.model FileField and save it to
       '/cache/model_{collection_id}.json'.
    4. Call VectorStoreIndex.load_from_disk with the cache_file_path.
    """
    # Retrieve the Collection object
    collection = await Collection.objects.aget(id=collection_id)
    logger.info(f"load_collection_model() - loaded collection {collection_id}")
    # Make sure there's a model
    if collection.model.name:
        logger.info("load_collection_model() - Setup local json index file")

        # Check if the JSON file exists
        cache_dir = Path(settings.BASE_DIR) / "cache"
        cache_file_path = cache_dir / f"model_{collection_id}.json"
        if not cache_file_path.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            with collection.model.open("rb") as model_file:
                with cache_file_path.open("w+", encoding="utf-8") as cache_file:
                    cache_file.write(model_file.read().decode("utf-8"))

                    
        storage_context,vector_store =get_storage_context(collection.db_storage,collection.uuid,True)

        index = VectorStoreIndex.from_vector_store(
            vector_store, storage_context=storage_context
        )

        logger.info("load_collection_model() - Load llama index")
        # index = GPTSimpleVectorIndex.load_from_disk(
        #     cache_file_path, service_context=service_context
        # )
        logger.info(
            "load_collection_model() - Llamaindex loaded and ready for query..."
        )

    else:
        logger.error(
            f"load_collection_model() - collection {collection_id} has no model!"
        )
        raise ValueError("No model exists for this collection!")

    return index

def get_storage_context(storage_choice: str,coll_uuid:UUID,vect_store = False):
    """
    Get the storage context based on the storage choice.
     Args:
        storage_choice (str):storage choice
        coll_name (str):Name of collection
    Returns:
        storage_context: The storage context

    """
    storage_context=None
    print(f"Storage Choice: {storage_choice} NEW CONFIG") 
    print(f"Storage Choice: {coll_uuid.hex} COLL NAME") 

    if storage_choice == "chromadb":
        db = chromadb.HttpClient(host='chroma', port=8001, settings=ChromaSettings(allow_reset=True, anonymized_telemetry=False))
        chroma_collection = db.get_or_create_collection(coll_uuid.hex)
        # assign chroma as the vector_store to the context
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
    elif storage_choice == "duckdb":
        print("Inside DuckDB")
        vector_store = DuckDBVectorStore(embed_dim=1536,database_name=coll_uuid.hex, persist_dir="./persist/")
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
    elif storage_choice == "milvus":
        print("Inside milvus")
        milvus_coll_name = 'a'+coll_uuid.hex;
        vector_store = MilvusVectorStore(uri="https://in03-3380cd4d85236db.api.gcp-us-west1.zillizcloud.com",token="a44d5f7122eb23e46571eb2354e727b55ce1e453593ae743397c43cb8bd6eec20bd58ed1611b9a999b5c208b72b8b502a422aefe",dim=1536, overwrite=False,collection_name=milvus_coll_name)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
    if(vect_store): return (storage_context,vector_store)
    else: return storage_context
