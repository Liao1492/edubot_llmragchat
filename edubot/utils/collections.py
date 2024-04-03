import logging
import textwrap
from pathlib import Path
import os
import openai
from django.core.files.base import ContentFile
import nest_asyncio
from django.conf import settings
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


from delphic.indexes.models import Collection

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


async def load_collection_model(collection_id: str | int) -> VectorStoreIndex:
    """
    Load the Collection model from cache or the database, and return the index.

    Args:
        collection_id (Union[str, int]): The ID of the Collection model instance.

    Returns:
        GPTSimpleVectorIndex: The loaded index.

    This function performs the following steps:
    1. Retrieve the Collection object with the given collection_id.
    2. Check if a JSON file with the name '/cache/model_{collection_id}.json' exists.
    3. If the JSON file doesn't exist, load the JSON from the Collection.model FileField and save it to
       '/cache/model_{collection_id}.json'.
    4. Call GPTSimpleVectorIndex.load_from_disk with the cache_file_path.
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

        # define LLM
        # logger.info(
        #     f"load_collection_model() - Setup service context with tokens {settings.MAX_TOKENS} and "
        #     f"model {settings.MODEL_NAME}"
        # )
        # initialize client
                    
        storage_context,vector_store =get_storage_context(collection.db_storage,collection.title,True)
        # db = chromadb.PersistentClient(path="./chroma_db")

        # get collection
        # chroma_collection = db.get_or_create_collection(collection.title)
        # print(chroma_collection)
        # assign chroma as the vector_store to the context
        # vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        # storage_context = StorageContext.from_defaults(vector_store=vector_store)
        # print(f"Storage Context: {storage_context}")
        index = VectorStoreIndex.from_vector_store(
            vector_store, storage_context=storage_context
        )

        # llm_predictor = LLMPredictor(
        #     llm=OpenAI(temperature=0, model_name="text-davinci-003", max_tokens=512)
        # )
        # service_context = ServiceContext.from_defaults(llm_predictor=llm_predictor)

        # Call GPTSimpleVectorIndex.load_from_disk
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

async def add_index_to_collection(collection_id: str | int, doc_file: ContentFile) -> None:
    """
    Add an index to a Collection model instance.

    Args:
        collection_id (Union[str, int]): The ID of the Collection model instance.
        index (GPTSimpleVectorIndex): The index to add to the Collection.

    This function performs the following steps:
    1. Retrieve the Collection object with the given collection_id.
    2. Save the index to the Collection.model FileField.
    """
    # Retrieve the Collection object
    collection = await Collection.objects.aget(id=collection_id)
    logger.info(f"add_index_to_collection() - loaded collection {collection_id}")

    # Save the index to the Collection
    with collection.model.open("wb") as model_file:
        index.save_to_disk(model_file)

    logger.info(f"add_index_to_collection() - saved index to collection {collection_id}")


async def query_collection(collection_id: str | int, query_str: str) -> str:
    """
    Query a collection with a given question and return the response as nicely-structured markdown text.

    Args:
        collection_id (Union[str, int]): The ID of the Collection model instance.
        query_str (str): The natural language question to query the collection.

    Returns:
        str: The response from the query as nicely-structured markdown text.

    This function performs the following steps:
    1. Load the GPTSimpleVectorIndex from the Collection with the given collection_id using load_collection_model.
    2. Call index.query with the query_str and get the llama_index.schema.Response object.
    3. Format the response and sources as markdown text and return the formatted text.
    """
    Settings.chunk_size = 512

    try:
        # Load the index from the collection
        index = await load_collection_model(collection_id)
        # create a query engine
        query_engine_tools=QueryEngineTool(
            query_engine=index.as_query_engine(),
            metadata=ToolMetadata(
                name=f"vector_index_collectionId_{collection_id}",
                description=f"Questioning about the collection with ID {collection_id}",
            ),
        )
        query_engine = SubQuestionQueryEngine.from_defaults(
            query_engine_tools=query_engine_tools,
            llm=OpenAI(model="gpt-4-0613"),
        )
        query_engine_tool = QueryEngineTool(
            query_engine=query_engine,
            metadata=ToolMetadata(
                name="sub_question_query_engine",
                description="useful for when you want to answer queries that require analyzing multiple SEC 10-K documents for Uber",
            ),
        )
        agent = OpenAIAgent.from_tools(query_engine_tool, verbose=True)

        # query_engine = index.as_query_engine()
        # Call index.query and return the response
        # response = query_engine.query(query_str)
        response = agent.chat(query_str)

        # Format the response as markdown
        markdown_response = f"## Response\n\n{response}\n\n"

        if response.source_nodes:
            markdown_sources = f"## Sources\n\n{response.get_formatted_sources()}"
        else:
            markdown_sources = ""

        formatted_response = f"{markdown_response}{markdown_sources}"

    except ValueError:
        formatted_response = "No model exists for this collection!"

    return formatted_response

def get_storage_context(storage_choice: str,coll_name:str,vect_store = False):
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
    print(f"Storage Choice: {coll_name} COLL NAME") 

    if storage_choice == "chromadb":
        db = chromadb.HttpClient(host='chroma', port=8001, settings=ChromaSettings(allow_reset=True, anonymized_telemetry=False))
        chroma_collection = db.get_or_create_collection(coll_name)
        # assign chroma as the vector_store to the context
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
    elif storage_choice == "duckdb":
        print("Inside DuckDB")
        vector_store = DuckDBVectorStore(embed_dim=1536,database_name=coll_name, persist_dir="./persist/")
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
    elif storage_choice == "milvus":
        print("Inside milvus")
        vector_store = MilvusVectorStore(uri="https://in03-3380cd4d85236db.api.gcp-us-west1.zillizcloud.com",token="a44d5f7122eb23e46571eb2354e727b55ce1e453593ae743397c43cb8bd6eec20bd58ed1611b9a999b5c208b72b8b502a422aefe",dim=1536, overwrite=False,collection_name=coll_name)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
    if(vect_store): return (storage_context,vector_store)
    else: return storage_context
