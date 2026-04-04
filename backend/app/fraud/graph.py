# Celery task: detect_ring_registrations runs daily at 02:00 IST
# Wired in app/tasks/celery_app.py by Person 3
# This function is imported there - do not add Celery imports here

from __future__ import annotations

from collections import defaultdict

import networkx as nx
from sqlalchemy.orm import Session

from app.models.worker import WorkerProfile


def detect_ring_registrations(db: Session) -> list[list[str]]:
    """Return connected worker groups that share device fingerprints or registration IPs."""
    rows = (
        db.query(
            WorkerProfile.id,
            WorkerProfile.device_fingerprint,
            WorkerProfile.registration_ip,
        )
        .all()
    )

    graph = nx.Graph()
    workers_by_device: dict[str, list[str]] = defaultdict(list)
    workers_by_ip: dict[str, list[str]] = defaultdict(list)

    for worker_id, device_fingerprint, registration_ip in rows:
        worker_id_str = str(worker_id)
        graph.add_node(worker_id_str)

        if device_fingerprint:
            workers_by_device[device_fingerprint].append(worker_id_str)
        if registration_ip:
            workers_by_ip[registration_ip].append(worker_id_str)

    # Pass 1: connect workers sharing the same device fingerprint.
    for group in workers_by_device.values():
        if len(group) > 1:
            anchor = group[0]
            for other_worker_id in group[1:]:
                graph.add_edge(anchor, other_worker_id)

    # Pass 2: connect workers sharing the same registration IP.
    for group in workers_by_ip.values():
        if len(group) > 1:
            anchor = group[0]
            for other_worker_id in group[1:]:
                graph.add_edge(anchor, other_worker_id)

    suspected_rings = [
        sorted(component)
        for component in nx.connected_components(graph)
        if len(component) > 1
    ]
    suspected_rings.sort(key=lambda component: (len(component), component))

    return suspected_rings
