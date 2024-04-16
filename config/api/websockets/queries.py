import json

from channels.generic.websocket import AsyncWebsocketConsumer
import openai
from urllib.parse import parse_qs
from edubot.utils.collections import load_collection_model
from edubot.utils.paths import extract_connection_id
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.llms.openai import OpenAI
from llama_index.core.query_engine import SubQuestionQueryEngine
from llama_index.llms.openai import OpenAI
from llama_index.core.query_pipeline import QueryPipeline
from llama_index.postprocessor.cohere_rerank import CohereRerank
from llama_index.core.response_synthesizers import TreeSummarize
from llama_index.core.query_pipeline import InputComponent
from llama_index.core import Settings
from django.conf import settings




class CollectionQueryConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        openai.api_key=settings.OPENAI_API
        query_string = self.scope["query_string"].decode()
        query_params = parse_qs(query_string)  
        self.model = query_params.get('model', [None])[0] 
        print(f"Model: {self.model}")
        openai.models=self.model
        print("Connecting...")  # Debugging print statement
        try:
            self.collection_id = extract_connection_id(self.scope["path"])
            print(f"Connect to collection model: {self.collection_id}")
            # define LLM
            # self.reranker = CohereRerank(api_key="ZADiotSrJwugGnVQZMztMv773UHwqPa4xRu6v6sU",top_n=2)
            print("After retriever")
            self.llm = OpenAI(model=self.model)
            self.index = await load_collection_model(self.collection_id)
            self.query_engine = self.index.as_query_engine()

            print(f"index: {self.index}")
            # print(f"Query: {modified_query_str}")
            print(f"Query: {self.query_engine}")
            print(f"Index loaded: {self.index}")
            await self.accept()
            print("Connected.")  # Debugging print statement
        except ValueError as e:
            print(f"Value error prevented model loading: {e}")
            await self.accept()
            await self.close(code=4000)
        except Exception as e:
            print(f"Error during connection: {e}")  # Debugging print statement

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        print(f"Received text_data_json: {text_data_json}")
        Settings.chunk_size = 512

        if self.index is not None:
            query_str = text_data_json["query"]
            enhanced = text_data_json.get("enhanced", False)
            top_k = text_data_json.get("top_k", 20)

            modified_query_str = f"""
            Please return a nicely formatted markdown string to this request:
            {query_str}
            """

            if(enhanced == 'Y'):
                try:
                    p = QueryPipeline(verbose=True)
                    print("After querypipeline")
                    retriever = self.index.as_retriever(similarity_top_k=top_k)
                    summarizer = TreeSummarize(llm=self.llm)

                    p.add_modules(
                        {
                            "input": InputComponent(),
                            "retriever": retriever,
                            "summarizer": summarizer,
                            # "reranker": self.reranker,
                        }
                    )
                    # p.add_link("input", "retriever")
                    # p.add_link("input", "summarizer", dest_key="query_str")
                    # p.add_link("retriever", "reranker", dest_key="nodes")
                    # p.add_link("reranker", "summarizer", dest_key="nodes")
                    p.add_link("input", "retriever")
                    p.add_link("input", "summarizer", dest_key="query_str")
                    p.add_link("retriever", "summarizer", dest_key="nodes")
                    print(f"Enhanced Query with {top_k}")
                    # response = self.query_engine.query(modified_query_str)
                    # print(f"Response : {response}")
                    # response = self.index.query(modified_query_str)
                    response=p.run(input=modified_query_str)
                    print("After resposne")
                except ValueError as e:
                    print(f"Value error prevented model loading: {e}")
                    await self.accept()
                    await self.close(code=4000)
                except Exception as e:
                    print(f"Error during connection: {e}")

                # Format the response as markdown
                markdown_response = f"## Response\n\n{response}\n\n"
                if response.source_nodes:
                    markdown_sources = f"## Sources\n\n{response.get_formatted_sources()}"
                else:
                    markdown_sources = ""

                formatted_response = f"{markdown_response}{markdown_sources}"

                await self.send(json.dumps({"response": formatted_response}, indent=4))
            else:
                response =self.query_engine.query(modified_query_str)
                print(f"Response : {response}")

                # response = self.index.query(modified_query_str)

                # Format the response as markdown
                markdown_response = f"## Response\n\n{response}\n\n"
                if response.source_nodes:
                    markdown_sources = f"## Sources\n\n{response.get_formatted_sources()}"
                else:
                    markdown_sources = ""

                formatted_response = f"{markdown_response}{markdown_sources}"

                await self.send(json.dumps({"response": formatted_response}, indent=4))
        else:
            await self.send(
                json.dumps({"error": "No index loaded for this connection."}, indent=4)
            )
