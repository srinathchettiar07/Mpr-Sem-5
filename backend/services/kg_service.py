import os
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class KGService:
    """Neo4j-backed mini knowledge graph for patients, visits, labs and medications.

    Optional: If NEO4J_URI or driver import fails, service is disabled.
    """

    def __init__(self) -> None:
        self.enabled = True
        self._driver = None

        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")

        if not (uri and user and password):
            self.enabled = False
            logger.info("KGService disabled: missing NEO4J_* env vars")
            return

        try:
            from neo4j import GraphDatabase  # type: ignore
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
        except Exception as e:
            self.enabled = False
            logger.warning("KGService disabled (driver error): %s", str(e))

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    def upsert_visit(self, patient_id: str, extracted_text: str, meds: List[str], labs: List[Tuple[str, str]], conditions: List[str]) -> bool:
        if not self.enabled or not self._driver:
            return False
        try:
            with self._driver.session() as session:
                session.execute_write(self._create_entities, patient_id, meds, labs, conditions)
            return True
        except Exception as e:
            logger.error("KGService.upsert_visit error: %s", str(e))
            return False

    @staticmethod
    def _create_entities(tx, patient_id: str, meds: List[str], labs: List[Tuple[str, str]], conditions: List[str]):
        tx.run("MERGE (p:Patient {patient_id: $pid})", pid=patient_id)
        tx.run("CREATE (v:Visit {id: randomUUID(), ts: datetime()})", pid=patient_id)
        tx.run("MATCH (p:Patient {patient_id: $pid}), (v:Visit) WHERE v.ts IS NOT NULL WITH p, v ORDER BY v.ts DESC LIMIT 1 MERGE (p)-[:HAS_VISIT]->(v)", pid=patient_id)

        for name in meds:
            tx.run("MATCH (p:Patient {patient_id: $pid}), (v:Visit) WHERE v.ts IS NOT NULL WITH p, v ORDER BY v.ts DESC LIMIT 1 MERGE (m:Medication {name: $name}) MERGE (v)-[:HAS_MED]->(m)", pid=patient_id, name=name)

        for lab_name, lab_value in labs:
            tx.run("MATCH (p:Patient {patient_id: $pid}), (v:Visit) WHERE v.ts IS NOT NULL WITH p, v ORDER BY v.ts DESC LIMIT 1 CREATE (l:LabResult {name: $name, value: $value}) MERGE (v)-[:HAS_LAB]->(l)", pid=patient_id, name=lab_name, value=lab_value)

        for cond in conditions:
            tx.run("MATCH (p:Patient {patient_id: $pid}), (v:Visit) WHERE v.ts IS NOT NULL WITH p, v ORDER BY v.ts DESC LIMIT 1 MERGE (c:Condition {name: $name}) MERGE (v)-[:HAS_CONDITION]->(c)", pid=patient_id, name=cond)

    # naive extraction, can be replaced with spaCy NER
    def extract_entities(self, text: str) -> Dict[str, Any]:
        meds = self._regex_find(text, r"\b(amlodipine|metformin|atorvastatin|aspirin|losartan)\b", flags=2)
        labs = self._regex_labs(text)
        conditions = self._regex_find(text, r"\b(stroke|hypertension|diabetes|avm|hemorrhage|hemiplegia|aphasia)\b", flags=2)
        return {"medications": meds, "labs": labs, "conditions": conditions}

    def _regex_find(self, text: str, pattern: str, flags: int = 0) -> List[str]:
        import re
        return list({m.group(0) for m in re.finditer(pattern, text, flags)})

    def _regex_labs(self, text: str) -> List[tuple]:
        import re
        out: List[tuple] = []
        # naive lab capture: e.g., Hb: 13.2 g/dL
        for m in re.finditer(r"\b(Hb|HbA1c|Glucose|Creatinine|LDL|HDL)\b[:\s]+([0-9]+\.?[0-9]*)\s*([a-zA-Z/%]+)?", text, re.IGNORECASE):
            out.append((m.group(1), (m.group(2) + (" " + (m.group(3) or "")).strip()).strip()))
        return out


