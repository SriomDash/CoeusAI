from typing import List, Dict, Any
from elasticsearch import helpers
from backend.config import settings
from backend.clients.elastic_search_client import elastic_bus

class ElasticService:
    @staticmethod
    async def bulk_insert_chunks(labeled_data: List[Dict[str, Any]]) -> int:
        """
        Connects to Elastic using the persistent bus, ensures the index exists, and inserts data.
        """
        if not labeled_data:
            return 0

        client = elastic_bus.get_client()

        try:
            index_name = settings.ELASTIC_SEARCH_INDEX 
            
            if not await client.indices.exists(index=index_name):
                print(f"Creating index: {index_name}...")
                mapping = {
                    "mappings": {
                        "properties": {
                            "user_id": {"type": "keyword"}, 
                            "job_id": {"type": "keyword"},   
                            "content": {"type": "text"},     
                            "summary": {"type": "text"},
                            "keywords": {"type": "text"},
                            "search_terms": {"type": "text"},
                            "created_at": {"type": "date"}
                        }
                    }
                }
                await client.indices.create(index=index_name, body=mapping)

            actions = []
            for i, item in enumerate(labeled_data):
                doc_id = f"{item['job_id']}_chunk_{i}"
                raw_meta = item.get('metadata', {})

                action = {
                    "_index": index_name,
                    "_id": doc_id,
                    "_source": {
                        "user_id": item['user_id'],
                        "job_id": item['job_id'],
                        "content": item['content'],
                        "summary": item.get('summary', ''),
                        "keywords": ", ".join(raw_meta.get('keywords', [])),
                        "search_terms": ", ".join(raw_meta.get('search_terms', [])),
                    }
                }
                actions.append(action)

            # 4. Execute Bulk Insert
            success_count, failed = await helpers.async_bulk(client, actions)
            
            if failed:
                print(f"Elastic Errors: {failed}")
            
            print(f"Indexed {success_count} documents in Elasticsearch.")
            return success_count

        except Exception as e:
            print(f"Elastic Service Error: {e}")
            raise e
            