"""RIFTWALKER — SEEDED EXPEDITION MAP GENERATION 0.7"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple

from core_systems import PlayerState
from narrative_systems import REGIONS


class RoomType(str, Enum):
    START = "start"
    COMBAT = "combat"
    ELITE = "elite"
    EVENT = "event"
    SHRINE = "shrine"
    MERCHANT = "merchant"
    REST = "rest"
    RIFT = "rift"
    TREASURE = "treasure"
    BOSS = "boss"
    SECRET = "secret"


@dataclass
class RoomNode:
    id: str
    depth: int
    room_type: RoomType
    threat: int
    reward: float
    connections: List[str] = field(default_factory=list)
    hidden: bool = False
    tags: List[str] = field(default_factory=list)


@dataclass
class ExpeditionMap:
    seed: int
    region_id: str
    nodes: Dict[str, RoomNode]
    start_id: str
    boss_id: str
    current_id: str
    visited: List[str] = field(default_factory=list)

    def next_nodes(self, include_hidden: bool = False) -> List[RoomNode]:
        current = self.nodes[self.current_id]
        return [self.nodes[node_id] for node_id in current.connections if include_hidden or not self.nodes[node_id].hidden]

    def move_to(self, node_id: str) -> bool:
        if node_id not in self.nodes[self.current_id].connections:
            return False
        self.current_id = node_id
        if node_id not in self.visited:
            self.visited.append(node_id)
        return True


ROOM_WEIGHTS: Tuple[Tuple[RoomType, float], ...] = (
    (RoomType.COMBAT, 44),
    (RoomType.ELITE, 10),
    (RoomType.EVENT, 12),
    (RoomType.SHRINE, 8),
    (RoomType.MERCHANT, 5),
    (RoomType.REST, 7),
    (RoomType.RIFT, 8),
    (RoomType.TREASURE, 6),
)


def _roll_room_type(rng: random.Random, depth: int, danger: int, previous: Optional[RoomType]) -> RoomType:
    options, weights = zip(*ROOM_WEIGHTS)
    local = list(weights)
    for i, room_type in enumerate(options):
        if room_type == previous and room_type in (RoomType.REST, RoomType.MERCHANT, RoomType.TREASURE):
            local[i] *= 0.15
        if room_type == RoomType.ELITE:
            local[i] *= 0.7 + danger * 0.18 + depth * 0.03
        if room_type == RoomType.RIFT:
            local[i] *= 0.8 + danger * 0.12
        if depth <= 2 and room_type == RoomType.ELITE:
            local[i] *= 0.25
    return rng.choices(options, weights=local, k=1)[0]


def generate_expedition_map(region_id: str, seed: int, difficulty: int = 1, main_length: int = 9) -> ExpeditionMap:
    if region_id not in REGIONS:
        raise ValueError(f"Região inválida: {region_id}")
    rng = random.Random(seed)
    danger = REGIONS[region_id].danger
    nodes: Dict[str, RoomNode] = {}
    start = RoomNode("room_00_start", 0, RoomType.START, 0, 1.0, tags=["entry"])
    nodes[start.id] = start
    previous_id = start.id
    previous_type: Optional[RoomType] = RoomType.START

    for depth in range(1, main_length + 1):
        room_type = _roll_room_type(rng, depth, danger, previous_type)
        node_id = f"room_{depth:02d}_main"
        threat = max(1, int((danger + difficulty) * 7 + depth * 2.2 + (8 if room_type == RoomType.ELITE else 0)))
        reward = round(1.0 + danger * 0.08 + depth * 0.025 + (0.35 if room_type in (RoomType.ELITE, RoomType.RIFT, RoomType.TREASURE) else 0), 3)
        node = RoomNode(node_id, depth, room_type, threat, reward, tags=[region_id])
        nodes[node_id] = node
        nodes[previous_id].connections.append(node_id)

        # Ramos opcionais em cerca de metade dos andares.
        if depth >= 2 and depth < main_length and rng.random() < 0.50:
            branch_type = _roll_room_type(rng, depth, danger, room_type)
            branch_id = f"room_{depth:02d}_branch"
            branch = RoomNode(branch_id, depth, branch_type, max(1, threat - 2), round(reward + 0.12, 3), tags=["optional", region_id])
            nodes[branch_id] = branch
            nodes[previous_id].connections.append(branch_id)
            branch.connections.append(node_id)

        # Sala secreta não bloqueia caminho principal.
        if depth >= 3 and rng.random() < 0.16:
            secret_id = f"room_{depth:02d}_secret"
            secret = RoomNode(secret_id, depth, RoomType.SECRET, max(1, threat // 2), round(reward + 0.50, 3), hidden=True, tags=["secret", region_id])
            nodes[secret_id] = secret
            nodes[node_id].connections.append(secret_id)

        previous_id = node_id
        previous_type = room_type

    boss_id = f"room_{main_length + 1:02d}_boss"
    boss = RoomNode(boss_id, main_length + 1, RoomType.BOSS, int((danger + difficulty + main_length) * 10), round(2.0 + danger * 0.15, 3), tags=["boss", region_id])
    nodes[boss_id] = boss
    nodes[previous_id].connections.append(boss_id)
    return ExpeditionMap(seed, region_id, nodes, start.id, boss_id, start.id, visited=[start.id])


def serialize_map(exp_map: ExpeditionMap) -> Dict[str, object]:
    return {
        "seed": exp_map.seed,
        "region_id": exp_map.region_id,
        "start_id": exp_map.start_id,
        "boss_id": exp_map.boss_id,
        "current_id": exp_map.current_id,
        "visited": list(exp_map.visited),
        "nodes": {
            node_id: {
                "id": n.id, "depth": n.depth, "room_type": n.room_type.value,
                "threat": n.threat, "reward": n.reward, "connections": list(n.connections),
                "hidden": n.hidden, "tags": list(n.tags),
            }
            for node_id, n in exp_map.nodes.items()
        },
    }


def deserialize_map(data: Dict[str, object]) -> ExpeditionMap:
    nodes: Dict[str, RoomNode] = {}
    for node_id, raw in dict(data["nodes"]).items():
        nodes[node_id] = RoomNode(
            raw["id"], int(raw["depth"]), RoomType(raw["room_type"]), int(raw["threat"]), float(raw["reward"]),
            list(raw["connections"]), bool(raw["hidden"]), list(raw["tags"]),
        )
    return ExpeditionMap(int(data["seed"]), str(data["region_id"]), nodes, str(data["start_id"]), str(data["boss_id"]), str(data["current_id"]), list(data.get("visited", [])))


def ensure_worldgen_state(state: PlayerState) -> Dict[str, object]:
    root = state.campaign.setdefault("world_generation", {})
    root.setdefault("active_map", None)
    root.setdefault("completed_seeds", [])
    root.setdefault("secrets_found", 0)
    return root


def begin_generated_expedition(state: PlayerState, region_id: str, seed: int, difficulty: int = 1, main_length: int = 9) -> ExpeditionMap:
    exp_map = generate_expedition_map(region_id, seed, difficulty, main_length)
    ensure_worldgen_state(state)["active_map"] = serialize_map(exp_map)
    return exp_map


def load_active_map(state: PlayerState) -> Optional[ExpeditionMap]:
    raw = ensure_worldgen_state(state).get("active_map")
    return deserialize_map(raw) if raw else None


def save_active_map(state: PlayerState, exp_map: ExpeditionMap) -> None:
    ensure_worldgen_state(state)["active_map"] = serialize_map(exp_map)


def complete_generated_expedition(state: PlayerState) -> None:
    root = ensure_worldgen_state(state)
    raw = root.get("active_map")
    if raw:
        root["completed_seeds"].append(raw["seed"])
        root["completed_seeds"] = root["completed_seeds"][-30:]
    root["active_map"] = None


def worldgen_summary() -> Dict[str, int]:
    return {"room_types": len(RoomType), "registered_regions": len(REGIONS)}
