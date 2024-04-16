from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.files.base import ContentFile
from django.http import HttpRequest
from ninja import File, Form, Router
import copy
from ninja.files import UploadedFile
from ninja_extra import NinjaExtraAPI
from edubot.utils.collections import is_pure_zip_file 
from ninja_jwt.controller import NinjaJWTDefaultController
import zipfile
from edubot.indexes.models import Collection, Document
from edubot.tasks import create_index,load_index
import os
from .auth.api_key import NinjaApiKeyAuth
from .ninja_types import (
    CollectionModelSchema,
    CollectionQueryInput,
    CollectionQueryOutput,
    CollectionStatusEnum,
)

collections_router = Router()

api = NinjaExtraAPI(
    title="GREMLIN Engine NLP Microservice",
    description="Chat-All-The-Docs is a LLM document model orchestration engine that makes it easy to vectorize a "
    "collection of documents and then build and serve discrete Llama-Index models for each collection to "
    "create bespoke, highly-targed chattable knowledge bases.",
    version="b0.9.0",
    auth=None if settings.OPEN_ACCESS_MODE else NinjaApiKeyAuth(),
)

api.add_router("/collections", collections_router)
api.register_controllers(NinjaJWTDefaultController)


@api.get(
    "/heartbeat",
    auth=None,
    response=bool,
    tags=["Misc"],
    summary="Return true if api is up and running.",
)
def check_heartbeat(request):
    return True


@collections_router.post("/create")
async def create_collection(
    request,
    title: str = Form(...),
    description: str = Form(...),
    files: list[UploadedFile] = File(...),
    storage: str = Form(...)
):
    print("___________")
    print(storage)

    print(request.headers.get('Authorization'))

    key = None if getattr(request, "auth", None) is None else request.auth
    if key is not None:
        key = await key
    print(f"API KEY and Test: {key}")
    collection_instance = Collection(
        # api_key=key,
        title=title,
        db_storage=storage,
        description=description,
        status=CollectionStatusEnum.QUEUED,
    )
    print(collection_instance.uuid)

    print("Created collection:")
    # print(f"is zip file: {is_pure_zip_file(files[0])}")

    
    print(collection_instance)

    await sync_to_async(collection_instance.save)()
    # splitted_file_name = os.path.split(files[0].filename)
    # print(splitted_file_name[1])
    # if 
    #     print("ZIP FILE")
    # uploaded_files =copy.deepcopy(files)
  
    if 'zip' in files[0].name:
        with zipfile.ZipFile(files[0], 'r') as zipf:
            # Extract all files first
            zipf.extractall()
            # List to hold file names and their contents
            files_and_contents = []
            # Iterate over each file name in the zip file
            for file_name in zipf.namelist():
                print(file_name)
                if("MACOSX" in file_name):
                    continue
                try:
                    # Attempt to open and read the file as text
                    with open(file_name, 'r', encoding='utf-8') as file:
                        content = file.read()
                except UnicodeDecodeError:
                    # If there's a decoding error, read the file as binary
                    with open(file_name, 'rb') as file:
                        content = file.read()  # This will be binary data
                files_and_contents.append((file_name, content))
        for file_name, content in files_and_contents:
            doc_file = ContentFile(content, file_name)
            document = Document(collection=collection_instance, file=doc_file)
            await sync_to_async(document.save)()
        for file_name, content in files_and_contents:
            os.remove(file_name)
    else:
        for uploaded_file in files:
            doc_data = uploaded_file.file.read()
            doc_file = ContentFile(doc_data, uploaded_file.name)
            document = Document(collection=collection_instance, file=doc_file)
            await sync_to_async(document.save)()
    create_index.si(collection_instance.id).apply_async()

    # result = await sync_to_async(CollectionModelSchema.from_orm)(collection_instance)
    return await sync_to_async(CollectionModelSchema)(
        id=collection_instance.id,
        uuid=collection_instance.uuid,
        db_storage=collection_instance.db_storage,
        title=collection_instance.title,
        description=collection_instance.description,
        status=collection_instance.status,
        created=collection_instance.created.isoformat(),
        modified=collection_instance.modified.isoformat(),
        processing=collection_instance.processing,
        has_model=bool(collection_instance.model.name),
        document_names=await sync_to_async(list)(
            await sync_to_async(collection_instance.documents.values_list)(
                "file", flat=True
            )
        )
        # Fetch document names directly
    )



@collections_router.get(
    "/available",
    response=list[CollectionModelSchema],
    summary="Get a list of all of the collections " "created with my api_key",
)
async def get_my_collections_view(request: HttpRequest):
    key = None if getattr(request, "auth", None) is None else request.auth
    if key is not None:
        key = await key
    print("API KEY:")
    collections = Collection.objects.all()
    # collections = await sync_to_async(Collection.objects.all)()
    # print(collections[0].db_storage)

    # print(collections[0].db_storage)
    return [
        {
            "id": collection.id,
            "uuid": collection.uuid,
            "title": collection.title,
            "db_storage": collection.db_storage,
            "description": collection.description,
            "status": collection.status,
            "created": collection.created.isoformat(),
            "modified": collection.modified.isoformat(),
            "processing": collection.processing,
            "has_model": bool(collection.model.name),
            "document_names": await sync_to_async(list)(
                await sync_to_async(collection.documents.values_list)("file", flat=True)
            ),
        }
        async for collection in collections
    ]


@collections_router.get(
    "/get/{collection_id}",
    response=CollectionModelSchema,
    summary="Get a collection by ID"
)
async def get_collection_by_id(request, collection_id: int):
    collection = await sync_to_async(Collection.objects.filter(id=collection_id).first)()
    
    if collection is None:
        return {"error": "Collection not found"}, 404
    
    print(f"Collection ID: {collection_id}")
    print(collection)
    
    # Fetch document names asynchronously
    document_names = await sync_to_async(list)(
        await sync_to_async(collection.documents.values_list)("file", flat=True)
    )
    print(collection.db_storage + "DB STORAGE")
    
    return {
        "id": collection.id,
        "uuid": collection.uuid,

        "title": collection.title,
        "db_storage": collection.db_storage,
        "description": collection.description,
        "status": collection.status,
        "created": collection.created.isoformat(),
        "modified": collection.modified.isoformat(),
        "processing": collection.processing,
        "has_model": bool(collection.model.name if collection.model else False),
        "document_names": document_names,
    }


@collections_router.post(
    "/{collection_id}/add_file", summary="Add a file to a collection"
)
async def add_file_to_collection(
    request,
    collection_id: int,
    file: UploadedFile = File(...),
    description: str = Form(...),
):
    collection = await sync_to_async(Collection.objects.get)(id=collection_id)

    doc_data = file.read()
    doc_file = ContentFile(doc_data, file.name)
    print(file.name)
    document = Document(collection=collection, file=doc_file, description=description)
    await sync_to_async(document.save)()
    load_index.si(collection_id,document.created).apply_async()


    return {"message": f"Added file {file.name} to collection {collection_id}"}
