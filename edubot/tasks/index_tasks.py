import logging
import os
import tempfile
import uuid
from pathlib import Path
from edubot.utils.collections import get_storage_context
from django.conf import settings
from django.core.files import File

# from langchain import OpenAI
# from llama_index import (
#     GPTSimpleVectorIndex,
#     LLMPredictor,
#     ServiceContext,
#     download_loader,
# )
import chromadb
# from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext


from config import celery_app
from edubot.indexes.models import Collection, CollectionStatus

logger = logging.getLogger(__name__)


@celery_app.task
def create_index(collection_id):
    """
    Celery task to create a GPTSimpleVectorIndex for a given Collection object.

    This task takes the ID of a Collection object, retrieves it from the
    database along with its related documents, and saves the document files
    to a temporary directory. Then, it creates a GPTSimpleVectorIndex using
    the provided code and saves the index to the Comparison.model FileField.

    Args:
        collection_id (int): The ID of the Collection object for which the
                             index should be created.

    Returns:
        bool: True if the index is created and saved successfully, False otherwise.
    """
    logger.error(f"Model Name: {settings.MODEL_NAME}")
    print(settings.MODEL_NAME)

    try:
        
        # Get the Collection object with related documents
        collection = Collection.objects.prefetch_related("documents").get(
            id=collection_id
        )

        collection.status = CollectionStatus.RUNNING

        collection.save()


        try:
            # Create a temporary directory to store the document files
            with tempfile.TemporaryDirectory() as tempdir:

                tempdir_path = Path(tempdir)

                # Save the document files to the temporary directory
                for document in collection.documents.all():
                    logger.error(f"Document: {document}")
                    logger.error(f"Document: {document.file.name}")

                    with document.file.open("rb") as f:
                        file_data = f.read()

                    temp_file_path = tempdir_path / document.file.name
                    temp_file_path.parent.mkdir(parents=True, exist_ok=True)
                    logger.error(f"Temp File Path: {temp_file_path}")
                    with temp_file_path.open("wb") as f:
                        f.write(file_data)
                # embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
                # Create the GPTSimpleVectorIndex
                filename_fn = lambda filename: {"file_name": filename}

                # SimpleDirectoryReader = download_loader("SimpleDirectoryReader")
                # loader = SimpleDirectoryReader(
                #     tempdir_path, recursive=True, exclude_hidden=False
                # )

                storage_choice = collection.db_storage
                storage_context = get_storage_context(storage_choice, collection.title)
                # db = chromadb.PersistentClient(path="./chroma_db")
                # chroma_collection = db.get_or_create_collection(collection.title)
                # assign chroma as the vector_store to the context
                # vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
                # storage_context = StorageContext.from_defaults(vector_store=vector_store)
                path_docs = "{}/{}/".format(tempdir, 'documents');
                logger.error(f"Path Docs: {path_docs}")
                documents = SimpleDirectoryReader(path_docs,filename_as_id=True).load_data()
                index = VectorStoreIndex.from_documents(
                    documents, storage_context=storage_context
                )
                # index.
                
                logger.error(f"Completed Indexing {index.summary}") 
                # Save the index_str to the Comparison.model FileField
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    # f.write(index_str.encode())
                    f.flush()
                    f.seek(0)
                    collection.model.save(f"model_{uuid.uuid4()}.json", File(f))
                    collection.status = CollectionStatus.COMPLETE
                    collection.save()
                # Delete the temporary index file
                logger.error(f"Vector Index")
                os.unlink(f.name)
            logger.error(f"End")

            collection.processing = False
            collection.save()

            return True

        except Exception as e:
            logger.error(f"Error creating index for collection {collection_id}: {e}")
            collection.status = CollectionStatus.ERROR
            collection.save()

            return False

    except Exception as e:
        logger.error(f"Error loading collection: {e}")
        return False

@celery_app.task
def load_index(collection_id, document_created):
    """
    Celery task to load a GPTSimpleVectorIndex for a given Collection object.

    This task takes the ID of a Collection object, retrieves it from the
    database, and loads the index from the Collection.model FileField.

    Args:
        collection_id (int): The ID of the Collection object for which the
                             index should be loaded.

    Returns:
        bool: True if the index is loaded successfully, False otherwise.
    """
    try:
        # Get the Collection object
        collection = Collection.objects.prefetch_related("documents").get(
            id=collection_id
        )
        logger.error(f"Collection: {collection.title}")
        document = collection.documents.filter(created=document_created).first()
        # logger.error(f"Doc: {documents}")
        logger.error(f"Doc: {document.file.name}")

        # Load the index from the Collection
        with tempfile.TemporaryDirectory() as tempdir:
            tempdir_path = Path(tempdir)
            with document.file.open("rb") as f:
                file_data = f.read()
            temp_file_path = tempdir_path / document.file.name
            temp_file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.error(f"Temp File Path: {temp_file_path}")
            with temp_file_path.open("wb") as f:
                f.write(file_data)

            storage_choice = collection.db_storage
            storage_context = get_storage_context(storage_choice, collection.title)
            # db = chromadb.PersistentClient(path="./chroma_db")
            # chroma_collection = db.get_or_create_collection(collection.title)
            # assign chroma as the vector_store to the context
            # vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            # storage_context = StorageContext.from_defaults(vector_store=vector_store)
            path_docs = "{}/{}/".format(tempdir, 'documents');
            logger.error(f"Path Docs: {path_docs}")
            documents = SimpleDirectoryReader(path_docs).load_data()
            index = VectorStoreIndex.from_documents(
                documents, storage_context=storage_context
            )


        return True

    except Exception as e:
        logger.error(f"Error loading index for collection {collection_id}: {e}")
        return False