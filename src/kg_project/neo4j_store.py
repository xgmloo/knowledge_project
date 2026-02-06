from __future__ import annotations

from neo4j import GraphDatabase

from .models import Entity, Relation, Subgraph


class Neo4jStore:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def init_constraints(self) -> None:
        cypher = """
        CREATE CONSTRAINT entity_name_unique IF NOT EXISTS
        FOR (e:Entity) REQUIRE e.name IS UNIQUE
        """
        with self.driver.session() as session:
            session.run(cypher)

    def upsert_entities(self, entities: list[Entity]) -> None:
        query = """
        UNWIND $rows AS row
        MERGE (e:Entity {name: row.name})
        ON CREATE SET e.type = row.type, e.description = row.description
        ON MATCH SET
          e.type = coalesce(e.type, row.type),
          e.description = coalesce(e.description, row.description)
        """
        rows = [e.model_dump() for e in entities]
        if not rows:
            return
        with self.driver.session() as session:
            session.run(query, rows=rows)

    def upsert_relations(self, relations: list[Relation]) -> None:
        query = """
        UNWIND $rows AS row
        MATCH (s:Entity {name: row.source})
        MATCH (t:Entity {name: row.target})
        MERGE (s)-[r:RELATED {type: row.type}]->(t)
        ON CREATE SET r.evidence = row.evidence
        ON MATCH SET r.evidence = coalesce(r.evidence, row.evidence)
        """
        rows = [r.model_dump() for r in relations]
        if not rows:
            return
        with self.driver.session() as session:
            session.run(query, rows=rows)

    def graph_stats(self) -> dict:
        query = """
        MATCH (e:Entity)
        WITH count(e) AS entity_count
        MATCH ()-[r:RELATED]->()
        RETURN entity_count, count(r) AS relation_count
        """
        with self.driver.session() as session:
            record = session.run(query).single()
            return {
                "entity_count": record["entity_count"] if record else 0,
                "relation_count": record["relation_count"] if record else 0,
            }

    def subgraph_by_keyword(self, keyword: str, limit: int = 80) -> Subgraph:
        query = """
        MATCH (n:Entity)
        WHERE toLower(n.name) CONTAINS toLower($keyword)
        OPTIONAL MATCH (n)-[r:RELATED]-(m:Entity)
        RETURN DISTINCT n, r, m
        LIMIT $limit
        """
        nodes = {}
        edges = []
        with self.driver.session() as session:
            records = session.run(query, keyword=keyword, limit=limit)
            for rec in records:
                for key in ["n", "m"]:
                    node = rec.get(key)
                    if node:
                        nodes[node.element_id] = {
                            "id": node.element_id,
                            "name": node.get("name"),
                            "type": node.get("type", "Concept"),
                        }
                rel = rec.get("r")
                if rel:
                    edges.append(
                        {
                            "source": rel.start_node.element_id,
                            "target": rel.end_node.element_id,
                            "type": rel.get("type", "RELATED"),
                        }
                    )
        return Subgraph(nodes=list(nodes.values()), edges=edges)
